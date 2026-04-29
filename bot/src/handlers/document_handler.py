"""Обработчик документов (PDF/DOCX/TXT/MD) в Telegram.

Защита (security fix 2026-04-29):
- magic-bytes проверка после download (не доверяем расширению из TG)
- subprocess sandbox + RLIMIT_AS для extract — закрывает PDF/DOCX bomb
"""
import os
import tempfile
import logging
import multiprocessing
import resource

import magic

from telegram import Update
from telegram.ext import MessageHandler, filters, ContextTypes

from models.database import get_or_create_user
from utils.conversation_manager import ConversationManager

logger = logging.getLogger(__name__)


# ──────────── ограничения и whitelist ────────────

MAX_FILE_SIZE = 10 * 1024 * 1024              # 10MB
MAX_EXTRACTED_TEXT_LEN = 2 * 1024 * 1024      # 2MB
MAX_PDF_PAGES = 200
MAX_DOCX_PARAGRAPHS = 5000
EXTRACT_TIMEOUT_SEC = 20
EXTRACT_MEM_LIMIT_BYTES = 512 * 1024 * 1024   # 512MB на child процесс

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".docx", ".md"}
ALLOWED_MIME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "text/plain": "txt",
    "text/markdown": "md",
}


# ──────────── subprocess sandbox extract ────────────

def _set_child_limits():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (EXTRACT_MEM_LIMIT_BYTES, EXTRACT_MEM_LIMIT_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (25, 30))
    except Exception as e:
        logger.warning("setrlimit failed in child: %s", e)


def _extract_pdf(path: str) -> str:
    import PyPDF2
    parts = []
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        if len(reader.pages) > MAX_PDF_PAGES:
            raise Exception(f"PDF слишком длинный ({len(reader.pages)} стр., максимум {MAX_PDF_PAGES})")
        for page in reader.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def _extract_docx(path: str) -> str:
    from docx import Document
    doc = Document(path)
    paras = doc.paragraphs
    if len(paras) > MAX_DOCX_PARAGRAPHS:
        raise Exception(f"DOCX слишком длинный ({len(paras)} параграфов, максимум {MAX_DOCX_PARAGRAPHS})")
    return "\n".join(p.text for p in paras)


def _extract_worker(path: str, file_type: str) -> str:
    if file_type == "pdf":
        return _extract_pdf(path)
    if file_type == "docx":
        return _extract_docx(path)
    raise Exception(f"Unsupported in worker: {file_type}")


def _extract_in_subprocess(path: str, file_type: str) -> str:
    ctx = multiprocessing.get_context("fork")
    with ctx.Pool(processes=1, initializer=_set_child_limits) as pool:
        async_result = pool.apply_async(_extract_worker, (path, file_type))
        try:
            text = async_result.get(timeout=EXTRACT_TIMEOUT_SEC)
        except multiprocessing.TimeoutError:
            pool.terminate()
            raise Exception("Обработка файла заняла слишком долго — возможно, он повреждён или слишком сложен")
        except Exception as e:
            pool.terminate()
            err = str(e)
            if "MemoryError" in err or "Cannot allocate" in err:
                raise Exception("Файл слишком сложный для обработки (память)")
            raise Exception(f"Не удалось извлечь текст: {err}")

    if not text or not text.strip():
        raise Exception("Не удалось извлечь текст из документа")
    if len(text) > MAX_EXTRACTED_TEXT_LEN:
        text = text[:MAX_EXTRACTED_TEXT_LEN] + "\n\n[...текст обрезан до 2MB...]"
    return text.strip()


def _extract_simple_text(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(MAX_EXTRACTED_TEXT_LEN).strip()
    except UnicodeDecodeError:
        with open(path, "r", encoding="cp1251") as f:
            return f.read(MAX_EXTRACTED_TEXT_LEN).strip()


def _process_document(path: str) -> tuple[str, str]:
    """Главный entry: validate MIME → extract → return (text, file_type).

    MIME magic-bytes доверие выше расширения: zip-архив, переименованный в .pdf,
    будет отвергнут.
    """
    try:
        mime = magic.from_file(path, mime=True)
    except Exception as e:
        raise Exception(f"Не удалось определить тип файла: {e}")

    file_type = ALLOWED_MIME_TYPES.get(mime)
    if not file_type:
        # libmagic иногда выдаёт text/plain для .md — fallback по расширению
        ext = os.path.splitext(path)[1].lower()
        if ext == ".md" and mime.startswith("text/"):
            file_type = "md"
        else:
            raise Exception(f"Неподдерживаемый тип файла (MIME: {mime})")

    if file_type in ("txt", "md"):
        return _extract_simple_text(path), file_type

    return _extract_in_subprocess(path, file_type), file_type


# ──────────── Telegram handler ────────────

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    document = update.message.document

    logger.info("Получен документ от %s: %s", user.first_name, document.file_name)

    try:
        await update.message.reply_text("📄 Обрабатываю документ...")

        db_user = await get_or_create_user(
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        )

        conversation_id = context.user_data.get('active_conversation_id')
        if not conversation_id:
            conversation = await ConversationManager.create_new_conversation(db_user.id)
            context.user_data['active_conversation_id'] = conversation.id
            conversation_id = conversation.id

        # 1. Размер
        if document.file_size and document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                f"❌ Файл слишком большой ({document.file_size // 1024} KB, максимум {MAX_FILE_SIZE // 1024} KB)"
            )
            return

        # 2. Расширение (быстрая отсечка перед download)
        file_ext = os.path.splitext(document.file_name or "")[1].lower()
        if file_ext not in ALLOWED_EXTENSIONS:
            await update.message.reply_text(
                f"❌ Неподдерживаемый тип файла: {file_ext or '(без расширения)'}\n"
                f"Поддерживаются: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
            return

        # 3. Download → temp file
        tg_file = await context.bot.get_file(document.file_id)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tf:
                temp_path = tf.name
                await tg_file.download_to_drive(temp_path)

            # 4. Magic-bytes + subprocess extract
            extracted_text, file_type = _process_document(temp_path)

            content = f"📄 Файл: {document.file_name}\n\n{extracted_text}"
            await ConversationManager.add_message(
                conversation_id=conversation_id,
                role="user",
                content=content,
                telegram_message_id=update.message.message_id,
            )

            await update.message.reply_text(
                f"✅ Документ обработан!\n"
                f"📊 Извлечено текста: {len(extracted_text)} символов\n"
                f"💬 Теперь можете задать вопрос по содержимому документа"
            )
        except Exception as inner_e:
            logger.warning("Ошибка обработки документа от %s: %s", user.id, inner_e)
            await update.message.reply_text(f"❌ {inner_e}")
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    except Exception as e:
        logger.error("Ошибка обработки документа: %s", e, exc_info=True)
        await update.message.reply_text(
            "❌ Ошибка при обработке документа. Попробуйте ещё раз."
        )


document_handler = MessageHandler(filters.Document.ALL, handle_document)

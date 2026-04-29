"""Извлечение текста из PDF/DOCX/TXT с защитой от decompression-bomb.

Защита: extract запускается в отдельном subprocess с RLIMIT_AS=512MB и
timeout=20s. Декомпрессионная бомба (1MB PDF → 10GB после inflate) убьёт
child-процесс по rlimit, не положив web-worker.

Лимиты:
  - размер файла до распаковки: 10MB (см. MAX_FILE_SIZE)
  - PDF: max 200 страниц
  - DOCX: max 5000 параграфов
  - text length после extract: max 2MB (защита от MEM/слишком большого
    LLM-контекста)
"""
import os
import multiprocessing
import resource
import logging
from typing import Optional, Tuple

import magic

logger = logging.getLogger(__name__)


# ──────────────── Public API ────────────────

class DocumentProcessor:
    """Главный класс — публичный API."""

    SUPPORTED_TYPES = {
        'application/pdf': 'pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'text/plain': 'txt',
        'text/markdown': 'md',
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024              # 10MB до распаковки
    MAX_EXTRACTED_TEXT_LEN = 2 * 1024 * 1024      # 2MB текста после extract
    MAX_PDF_PAGES = 200
    MAX_DOCX_PARAGRAPHS = 5000
    EXTRACT_TIMEOUT_SEC = 20
    EXTRACT_MEM_LIMIT_BYTES = 512 * 1024 * 1024   # 512MB на child процесс

    @staticmethod
    def detect_file_type(file_path: str) -> Optional[str]:
        try:
            mime_type = magic.from_file(file_path, mime=True)
            return DocumentProcessor.SUPPORTED_TYPES.get(mime_type)
        except Exception:
            return None

    @staticmethod
    def process_document(file_path: str) -> Tuple[str, str]:
        """Главный entry point. Возвращает (extracted_text, file_type).

        При превышении лимитов / повреждённом файле — поднимает Exception
        с понятным сообщением для юзера.
        """
        if not os.path.exists(file_path):
            raise Exception("Файл не найден")

        if os.path.getsize(file_path) > DocumentProcessor.MAX_FILE_SIZE:
            raise Exception("Файл слишком большой (максимум 10MB)")

        file_type = DocumentProcessor.detect_file_type(file_path)
        if not file_type:
            raise Exception("Неподдерживаемый тип файла")

        # txt/md небольшие, без forking
        if file_type in ('txt', 'md'):
            return _extract_text_simple(file_path), file_type

        # pdf/docx — sandboxed subprocess
        text = _extract_in_subprocess(file_path, file_type)
        return text, file_type


# ──────────────── Subprocess sandbox ────────────────

def _set_child_limits():
    """Запускается в child процессе перед extract'ом — режет RAM/CPU.

    Если PDF/DOCX оказался bomb'ом (распакуется в гигабайты) — child упадёт
    по MemoryError, не утянув web-worker.
    """
    try:
        # Address space (виртуальная память)
        resource.setrlimit(
            resource.RLIMIT_AS,
            (DocumentProcessor.EXTRACT_MEM_LIMIT_BYTES, DocumentProcessor.EXTRACT_MEM_LIMIT_BYTES),
        )
        # CPU time — hardlimit на 30s, soft на 25s
        resource.setrlimit(resource.RLIMIT_CPU, (25, 30))
    except Exception as e:
        # На некоторых платформах (особенно в контейнерах с ограничениями)
        # setrlimit может упасть — лимит cgroup и так есть, продолжаем без хард-лимита.
        logger.warning("setrlimit failed in child: %s", e)


def _extract_worker(file_path: str, file_type: str) -> str:
    """Запускается в child. Возвращает extracted text."""
    if file_type == 'pdf':
        return _extract_pdf(file_path)
    elif file_type == 'docx':
        return _extract_docx(file_path)
    raise Exception(f"Unsupported in worker: {file_type}")


def _extract_in_subprocess(file_path: str, file_type: str) -> str:
    """Запускает extract в отдельном процессе с timeout + memory limit."""
    ctx = multiprocessing.get_context("fork")  # Linux: fork — быстро (~5ms)
    with ctx.Pool(processes=1, initializer=_set_child_limits) as pool:
        async_result = pool.apply_async(_extract_worker, (file_path, file_type))
        try:
            text = async_result.get(timeout=DocumentProcessor.EXTRACT_TIMEOUT_SEC)
        except multiprocessing.TimeoutError:
            pool.terminate()
            raise Exception("Обработка файла заняла слишком долго — возможно, он повреждён или слишком сложен")
        except Exception as e:
            pool.terminate()
            # MemoryError из child → "файл слишком сложный"
            err_text = str(e)
            if "MemoryError" in err_text or "Cannot allocate" in err_text:
                raise Exception("Файл слишком сложный для обработки (память)")
            raise Exception(f"Не удалось извлечь текст: {err_text}")

    if not text or not text.strip():
        raise Exception("Не удалось извлечь текст из документа")

    if len(text) > DocumentProcessor.MAX_EXTRACTED_TEXT_LEN:
        text = text[:DocumentProcessor.MAX_EXTRACTED_TEXT_LEN] + "\n\n[...текст обрезан до 2MB...]"

    return text.strip()


# ──────────────── Per-format extractors (запускаются в child) ────────────────

def _extract_pdf(file_path: str) -> str:
    import PyPDF2
    text_parts = []
    with open(file_path, 'rb') as f:
        reader = PyPDF2.PdfReader(f)
        n_pages = len(reader.pages)
        if n_pages > DocumentProcessor.MAX_PDF_PAGES:
            raise Exception(f"PDF слишком длинный ({n_pages} страниц, максимум "
                            f"{DocumentProcessor.MAX_PDF_PAGES})")
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts)


def _extract_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    paras = doc.paragraphs
    if len(paras) > DocumentProcessor.MAX_DOCX_PARAGRAPHS:
        raise Exception(f"DOCX слишком длинный ({len(paras)} параграфов, максимум "
                        f"{DocumentProcessor.MAX_DOCX_PARAGRAPHS})")
    return "\n".join(p.text for p in paras)


def _extract_text_simple(file_path: str) -> str:
    """Простой txt/md — без subprocess (там нечему bomb'ить)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read(DocumentProcessor.MAX_EXTRACTED_TEXT_LEN).strip()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='cp1251') as f:
            return f.read(DocumentProcessor.MAX_EXTRACTED_TEXT_LEN).strip()

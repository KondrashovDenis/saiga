import os
import tempfile
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from database import db
from models.conversation import Conversation
from models.message import Message
from utils.document_processor import DocumentProcessor
from utils.file_validator import FileValidator

# Создаем blueprint для загрузки файлов
file_upload_bp = Blueprint('file_upload', __name__, url_prefix='/api/files')

@file_upload_bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Загрузка и обработка файла"""
    try:
        # Проверяем наличие файла
        if 'file' not in request.files:
            return jsonify({'error': 'Файл не найден в запросе'}), 400
        
        file = request.files['file']
        conversation_id = request.form.get('conversation_id')
        
        if not conversation_id:
            return jsonify({'error': 'ID диалога обязателен'}), 400
        
        # Проверяем права доступа к диалогу
        conversation = db.session.query(Conversation).get_or_404(conversation_id)
        if conversation.user_id != current_user.id:
            return jsonify({'error': 'Доступ запрещен'}), 403
        
        # Валидируем файл
        is_valid, validation_message = FileValidator.validate_file(file)
        if not is_valid:
            return jsonify({'error': validation_message}), 400
        
        # Сохраняем файл во временную директорию
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
                temp_path = temp_file.name
                file.seek(0)
                temp_file.write(file.read())
            
            # Обрабатываем документ
            extracted_text, file_type = DocumentProcessor.process_document(temp_path)
            
            # Создаем сообщение с извлеченным текстом
            filename = FileValidator.secure_filename_custom(file.filename)
            content = f"📄 Загружен файл: {filename}\n\n{extracted_text}"
            
            # Сохраняем сообщение в базу данных
            message = Message(
                conversation_id=conversation_id,
                role='user',
                content=content
            )
            db.session.add(message)
            db.session.commit()
            
            # Обновляем время последнего обновления диалога
            conversation.updated_at = message.timestamp
            db.session.commit()
            
            return jsonify({
                'success': True,
                'extracted_text': extracted_text,
                'filename': filename,
                'file_type': file_type,
                'text_length': len(extracted_text),
                'message_id': message.id
            })
            
        finally:
            # Удаляем временный файл
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
    
    except Exception as e:
        return jsonify({
            'error': 'Ошибка обработки файла',
            'details': str(e)
        }), 500

@file_upload_bp.route('/supported-types', methods=['GET'])
@login_required
def get_supported_types():
    """Возвращает список поддерживаемых типов файлов"""
    return jsonify({
        'extensions': list(FileValidator.ALLOWED_EXTENSIONS),
        'max_size_mb': FileValidator.MAX_FILE_SIZE // (1024 * 1024),
        'mime_types': list(FileValidator.ALLOWED_MIME_TYPES)
    })

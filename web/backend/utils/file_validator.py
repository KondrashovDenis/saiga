import os
import magic
from werkzeug.utils import secure_filename
from typing import Tuple

class FileValidator:
    """Класс для валидации загружаемых файлов"""
    
    ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx', 'md'}
    ALLOWED_MIME_TYPES = {
        'application/pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'text/plain',
        'text/markdown'
    }
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        """Проверяет допустимое расширение файла"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in FileValidator.ALLOWED_EXTENSIONS
    
    @staticmethod
    def validate_file(file) -> Tuple[bool, str]:
        """Полная валидация файла"""
        if not file:
            return False, "Файл не выбран"
        
        if not file.filename:
            return False, "Имя файла отсутствует"
        
        if not FileValidator.allowed_file(file.filename):
            return False, f"Неподдерживаемый тип файла. Разрешены: {', '.join(FileValidator.ALLOWED_EXTENSIONS)}"
        
        # Сохраняем во временный файл для проверки
        temp_path = None
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_path = temp_file.name
                file.seek(0)
                temp_file.write(file.read())
            
            # Проверяем размер
            if os.path.getsize(temp_path) > FileValidator.MAX_FILE_SIZE:
                return False, "Файл слишком большой (максимум 10MB)"
            
            # Проверяем MIME тип
            mime_type = magic.from_file(temp_path, mime=True)
            if mime_type not in FileValidator.ALLOWED_MIME_TYPES:
                return False, f"Неподдерживаемый MIME тип: {mime_type}"
            
            return True, "Файл валиден"
            
        except Exception as e:
            return False, f"Ошибка валидации: {str(e)}"
        finally:
            # Удаляем временный файл
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass
    
    @staticmethod
    def secure_filename_custom(filename: str) -> str:
        """Безопасное имя файла с сохранением кириллицы"""
        import re
        
        # Удаляем путь
        filename = os.path.basename(filename)
        
        # Заменяем пробелы на подчеркивания
        filename = re.sub(r'\s+', '_', filename)
        
        # Удаляем опасные символы, но сохраняем кириллицу
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        return filename

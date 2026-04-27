import os
import magic
import PyPDF2
from docx import Document
from typing import Optional, Tuple

class DocumentProcessor:
    """Общий класс для обработки различных типов документов"""
    
    SUPPORTED_TYPES = {
        'application/pdf': 'pdf',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'text/plain': 'txt',
        'text/markdown': 'md'
    }
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @staticmethod
    def detect_file_type(file_path: str) -> Optional[str]:
        """Определяет тип файла"""
        try:
            mime_type = magic.from_file(file_path, mime=True)
            return DocumentProcessor.SUPPORTED_TYPES.get(mime_type)
        except Exception:
            return None
    
    @staticmethod
    def extract_text_from_pdf(file_path: str) -> str:
        """Извлекает текст из PDF"""
        text = ""
        try:
            with open(file_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
        except Exception as e:
            raise Exception(f"Ошибка чтения PDF: {str(e)}")
        return text.strip()
    
    @staticmethod
    def extract_text_from_docx(file_path: str) -> str:
        """Извлекает текст из Word документа"""
        try:
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            raise Exception(f"Ошибка чтения DOCX: {str(e)}")
    
    @staticmethod
    def extract_text_from_txt(file_path: str) -> str:
        """Читает обычный текстовый файл"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
        except UnicodeDecodeError:
            with open(file_path, 'r', encoding='cp1251') as file:
                return file.read().strip()
        except Exception as e:
            raise Exception(f"Ошибка чтения TXT: {str(e)}")
    
    @staticmethod
    def process_document(file_path: str) -> Tuple[str, str]:
        """Основной метод обработки документа"""
        if not os.path.exists(file_path):
            raise Exception("Файл не найден")
        
        if os.path.getsize(file_path) > DocumentProcessor.MAX_FILE_SIZE:
            raise Exception("Файл слишком большой (максимум 10MB)")
        
        file_type = DocumentProcessor.detect_file_type(file_path)
        if not file_type:
            raise Exception("Неподдерживаемый тип файла")
        
        if file_type == 'pdf':
            text = DocumentProcessor.extract_text_from_pdf(file_path)
        elif file_type == 'docx':
            text = DocumentProcessor.extract_text_from_docx(file_path)
        elif file_type in ['txt', 'md']:
            text = DocumentProcessor.extract_text_from_txt(file_path)
        else:
            raise Exception(f"Обработчик для типа {file_type} не реализован")
        
        if not text.strip():
            raise Exception("Не удалось извлечь текст из документа")
        
        return text, file_type

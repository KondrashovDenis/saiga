import uuid
from datetime import datetime

from database import db

class Conversation(db.Model):
    """Модель диалога"""
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False, default="Новый диалог")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    model_used = db.Column(db.String(100), nullable=True)
    is_shared = db.Column(db.Boolean, default=False)
    share_token = db.Column(db.String(64), unique=True, nullable=True)
    
    # Отношения с другими таблицами
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', 
                               cascade='all, delete-orphan', order_by='Message.timestamp')
    
    def __init__(self, user_id, title="Новый диалог", model_used=None):
        self.user_id = user_id
        self.title = title
        self.model_used = model_used
        
    def generate_share_token(self):
        """Генерирует токен для шаринга диалога"""
        self.share_token = str(uuid.uuid4())
        self.is_shared = True
        return self.share_token
    
    def disable_sharing(self):
        """Отключает шаринг диалога"""
        self.share_token = None
        self.is_shared = False
    
    def to_dict(self):
        """Преобразует диалог в словарь для API"""
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'model_used': self.model_used,
            'is_shared': self.is_shared,
            'message_count': self.messages.count()
        }
    
    def __repr__(self):
        return f'<Conversation {self.title}>'

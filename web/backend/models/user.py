from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from database import db

class User(db.Model, UserMixin):
    """Модель пользователя с поддержкой Telegram аутентификации"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(128), nullable=True)
    
    # Telegram данные
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=True, index=True)
    telegram_username = db.Column(db.String(64), nullable=True)
    first_name = db.Column(db.String(64), nullable=True)
    last_name = db.Column(db.String(64), nullable=True)
    language_code = db.Column(db.String(10), default='ru')
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    
    # Способ регистрации: 'email', 'telegram', 'both'
    auth_method = db.Column(db.String(20), default='email')
    
    # Отношения с другими таблицами
    conversations = db.relationship('Conversation', backref='user', lazy='dynamic', 
                                    cascade='all, delete-orphan')
    settings = db.relationship('Setting', backref='user', uselist=False, 
                               cascade='all, delete-orphan')
    
    def __init__(self, username=None, email=None, password=None, telegram_id=None, 
                 telegram_username=None, first_name=None, last_name=None, is_admin=False):
        self.username = username
        self.email = email
        self.telegram_id = telegram_id
        self.telegram_username = telegram_username
        self.first_name = first_name
        self.last_name = last_name
        self.is_admin = is_admin
        
        if password:
            self.set_password(password)
            
        # Определяем способ аутентификации
        if telegram_id and (email or username):
            self.auth_method = 'both'
        elif telegram_id:
            self.auth_method = 'telegram'
        else:
            self.auth_method = 'email'
    
    def set_password(self, password):
        """Устанавливает хэш пароля"""
        if password:
            self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Проверяет пароль"""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def link_telegram(self, telegram_id, telegram_username=None, first_name=None, last_name=None):
        """Привязывает Telegram аккаунт к существующему пользователю"""
        self.telegram_id = telegram_id
        self.telegram_username = telegram_username
        self.first_name = first_name
        self.last_name = last_name
        
        if self.auth_method == 'email':
            self.auth_method = 'both'
    
    def unlink_telegram(self):
        """Отвязывает Telegram аккаунт"""
        self.telegram_id = None
        self.telegram_username = None
        
        if self.auth_method == 'both':
            self.auth_method = 'email'
        elif self.auth_method == 'telegram':
            # Нельзя отвязать единственный способ входа
            return False
        return True
    
    @property
    def display_name(self):
        """Возвращает имя для отображения"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return self.username
        elif self.telegram_username:
            return f"@{self.telegram_username}"
        else:
            return f"User {self.id}"
    
    @property
    def can_login_with_password(self):
        """Может ли пользователь войти с паролем"""
        return self.password_hash is not None
    
    @property
    def can_login_with_telegram(self):
        """Может ли пользователь войти через Telegram"""
        return self.telegram_id is not None
    
    @staticmethod
    def find_by_telegram_id(telegram_id):
        """Найти пользователя по Telegram ID"""
        return User.query.filter_by(telegram_id=telegram_id).first()
    
    @staticmethod
    def find_by_email(email):
        """Найти пользователя по email"""
        return User.query.filter_by(email=email).first()
    
    @staticmethod
    def find_by_username(username):
        """Найти пользователя по username"""
        return User.query.filter_by(username=username).first()
    
    def __repr__(self):
        return f'<User {self.display_name}>'

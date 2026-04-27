import json
from database import db

class Setting(db.Model):
    """Модель пользовательских настроек"""
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Настройки интерфейса
    ui_theme = db.Column(db.String(20), default='auto')  # 'light', 'dark', 'auto'
    avatar_style = db.Column(db.String(20), default='initials')  # 'initials', 'gravatar', 'custom'
    message_animations = db.Column(db.Boolean, default=True)
    auto_scroll = db.Column(db.Boolean, default=True)
    show_timestamps = db.Column(db.Boolean, default=True)
    show_quick_replies = db.Column(db.Boolean, default=True)
    enable_reactions = db.Column(db.Boolean, default=True)
    markdown_support = db.Column(db.Boolean, default=True)
    
    # Настройки модели в формате JSON
    model_preferences_json = db.Column(db.Text, default='{}')
    
    # Отдельные параметры модели для быстрого доступа
    temperature = db.Column(db.Float, default=0.7)
    top_p = db.Column(db.Float, default=0.9)
    
    def __init__(self, user_id, **kwargs):
        self.user_id = user_id
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        if not self.model_preferences_json:
            self.model_preferences_json = '{}'
    
    @property
    def model_preferences(self):
        """Получает настройки модели в виде словаря"""
        try:
            return json.loads(self.model_preferences_json)
        except:
            return {}
    
    @model_preferences.setter
    def model_preferences(self, preferences_dict):
        """Устанавливает настройки модели из словаря"""
        self.model_preferences_json = json.dumps(preferences_dict)
    
    def to_dict(self):
        """Преобразует настройки в словарь для API"""
        return {
            'ui_theme': self.ui_theme,
            'avatar_style': self.avatar_style,
            'message_animations': self.message_animations,
            'auto_scroll': self.auto_scroll,
            'show_timestamps': self.show_timestamps,
            'show_quick_replies': self.show_quick_replies,
            'enable_reactions': self.enable_reactions,
            'markdown_support': self.markdown_support,
            'temperature': self.temperature,
            'top_p': self.top_p,
            'model_preferences': self.model_preferences
        }
    
    def __repr__(self):
        return f'<Setting user_id={self.user_id}>'

from sqlalchemy import Column, Integer, String, Boolean, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class Setting(Base):
    __tablename__ = 'settings'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False, unique=True)
    
    # LLM настройки
    temperature = Column(Float, default=0.7)
    top_p = Column(Float, default=0.9)
    max_tokens = Column(Integer, default=2048)
    
    # Интерфейс
    language = Column(String(10), default='ru')
    notifications_enabled = Column(Boolean, default=True)
    quick_replies_enabled = Column(Boolean, default=True)
    
    # Связи
    user = relationship("User", backref="settings")
    
    def __repr__(self):
        return f'<Setting user_id={self.user_id}>'

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class Message(Base):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
    role = Column(String(20), nullable=False)  # 'user' или 'assistant'
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Telegram специфичные поля
    telegram_message_id = Column(Integer, nullable=True)
    message_type = Column(String(20), default='text')  # 'text', 'voice', 'document'
    
    # Связи
    conversation = relationship("Conversation", back_populates="messages")
    
    def __repr__(self):
        return f'<Message {self.id} ({self.role})>'

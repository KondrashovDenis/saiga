from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload
from models.database import async_session
from models.user import User
from models.conversation import Conversation
from models.message import Message
from typing import Optional, List

class ConversationManager:
    @staticmethod
    async def get_or_create_active_conversation(user_id: int) -> Conversation:
        async with async_session() as session:
            stmt = select(Conversation).where(
                Conversation.user_id == user_id,
                Conversation.is_active == True
            ).order_by(desc(Conversation.updated_at))
            
            result = await session.execute(stmt)
            conversation = result.scalar_one_or_none()
            
            if not conversation:
                conversation = Conversation(user_id=user_id, title="Новый диалог")
                session.add(conversation)
                await session.commit()
                await session.refresh(conversation)
            
            return conversation
    
    @staticmethod
    async def create_new_conversation(user_id: int, title: str = "Новый диалог") -> Conversation:
        async with async_session() as session:
            conversation = Conversation(user_id=user_id, title=title)
            session.add(conversation)
            await session.commit()
            await session.refresh(conversation)
            return conversation
    
    @staticmethod
    async def get_user_conversations(user_id: int, limit: int = 10) -> List[Conversation]:
        async with async_session() as session:
            stmt = select(Conversation).where(
                Conversation.user_id == user_id
            ).options(
                selectinload(Conversation.messages)
            ).order_by(desc(Conversation.updated_at)).limit(limit)
            
            result = await session.execute(stmt)
            return result.scalars().all()
    
    @staticmethod
    async def add_message(conversation_id: int, role: str, content: str, telegram_message_id: int = None) -> Message:
        async with async_session() as session:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                telegram_message_id=telegram_message_id
            )
            session.add(message)
            
            conversation = await session.get(Conversation, conversation_id)
            if conversation:
                conversation.updated_at = message.timestamp
                if conversation.title == "Новый диалог" and role == "user":
                    conversation.title = content[:50] + ("..." if len(content) > 50 else "")
            
            await session.commit()
            await session.refresh(message)
            return message
    
    @staticmethod
    async def get_conversation_messages(conversation_id: int) -> List[Message]:
        async with async_session() as session:
            stmt = select(Message).where(
                Message.conversation_id == conversation_id
            ).order_by(Message.timestamp)
            
            result = await session.execute(stmt)
            return result.scalars().all()

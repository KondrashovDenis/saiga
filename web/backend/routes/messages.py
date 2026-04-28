from flask import Blueprint, request, jsonify, abort
from flask_login import login_required, current_user

from database import db
from models.conversation import Conversation
from models.message import Message

# Создаем blueprint для сообщений
messages_bp = Blueprint('messages', __name__, url_prefix='/api/conversations')

@messages_bp.route('/<int:conversation_id>/messages', methods=['GET'])
@login_required
def get_messages(conversation_id):
    """Получает все сообщения диалога"""
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    
    # Проверяем, принадлежит ли диалог текущему пользователю или является ли он публичным
    if conversation.user_id != current_user.id and not conversation.is_shared:
        abort(403)
    
    # Получаем сообщения
    messages = conversation.messages.order_by(Message.timestamp).all()
    
    # Преобразуем сообщения в формат JSON
    messages_json = [message.to_dict() for message in messages]
    
    return jsonify(messages_json)

@messages_bp.route('/<int:conversation_id>/messages', methods=['POST'])
@login_required
def add_message(conversation_id):
    """Добавляет новое сообщение в диалог"""
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    
    # Проверяем, принадлежит ли диалог текущему пользователю
    if conversation.user_id != current_user.id:
        abort(403)
    
    # Получаем данные из запроса
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify({'error': 'Неверный формат данных'}), 400
    
    # Проверяем лимит на количество сообщений
    from config import Config
    if conversation.messages.count() >= Config.MAX_MESSAGES_PER_CONVERSATION:
        return jsonify({
            'error': 'Достигнуто максимальное количество сообщений. Пожалуйста, создайте новый диалог.'
        }), 400
    
    # Создаем сообщение пользователя
    message = Message(
        conversation_id=conversation_id,
        role='user',
        content=data['content']
    )
    
    db.session.add(message)
    db.session.commit()
    
    # Обновляем время последнего обновления диалога
    conversation.updated_at = message.timestamp
    db.session.commit()
    
    return jsonify(message.to_dict())

@messages_bp.route('/<int:conversation_id>/messages/<int:message_id>', methods=['DELETE'])
@login_required
def delete_message(conversation_id, message_id):
    """Удаляет сообщение из диалога"""
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    
    # Проверяем, принадлежит ли диалог текущему пользователю
    if conversation.user_id != current_user.id:
        abort(403)
    
    message = db.session.query(Message).get_or_404(message_id)
    
    # Проверяем, принадлежит ли сообщение указанному диалогу
    if message.conversation_id != conversation_id:
        abort(404)
    
    db.session.delete(message)
    db.session.commit()
    
    return jsonify({'success': True})

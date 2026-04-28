from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import desc

from database import db
from models.conversation import Conversation
from models.message import Message
from models.setting import Setting

# Создаем blueprint для диалогов
conversations_bp = Blueprint('conversations', __name__, url_prefix='/conversations')

@conversations_bp.route('/')
@login_required
def list():
    """Отображает список диалогов пользователя"""
    conversations = db.session.query(Conversation).filter_by(user_id=current_user.id) \
                                     .order_by(desc(Conversation.updated_at)) \
                                     .all()
    return render_template('chat/conversations_list.html', conversations=conversations)

@conversations_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    """Создает новый диалог"""
    if request.method == 'POST':
        title = request.form.get('title', 'Новый диалог')
        model_used = request.form.get('model', 'saiga_nemo_12b')
        
        # Проверяем лимит на количество диалогов
        from config import Config
        if db.session.query(Conversation).filter_by(user_id=current_user.id).count() >= Config.MAX_CONVERSATIONS_PER_USER:
            flash('Вы достигли максимального количества диалогов. Пожалуйста, удалите ненужные диалоги.', 'warning')
            return redirect(url_for('conversations.list'))
        
        conversation = Conversation(user_id=current_user.id, title=title, model_used=model_used)
        db.session.add(conversation)
        db.session.commit()
        
        return redirect(url_for('conversations.view', conversation_id=conversation.id))
    
    return render_template('chat/new_conversation.html')

@conversations_bp.route('/<int:conversation_id>')
@login_required
def view(conversation_id):
    """Отображает диалог"""
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    
    # Проверяем, принадлежит ли диалог текущему пользователю
    if conversation.user_id != current_user.id and not conversation.is_shared:
        abort(403)
    
    # Получаем сообщения
    messages = conversation.messages.order_by(Message.timestamp).all()
    
    # Определяем, является ли пользователь владельцем диалога
    is_owner = conversation.user_id == current_user.id

    # Получаем настройки пользователя
    user_settings = db.session.query(Setting).filter_by(user_id=current_user.id).first()
    if not user_settings:
        user_settings = Setting(user_id=current_user.id)
        db.session.add(user_settings)
        db.session.commit()
    
    return render_template('chat/conversation.html', 
                          conversation=conversation, 
                          messages=messages,
                          is_owner=is_owner,
                          user_settings=user_settings)

@conversations_bp.route('/<int:conversation_id>/delete', methods=['POST'])
@login_required
def delete(conversation_id):
    """Удаляет диалог"""
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    
    # Проверяем, принадлежит ли диалог текущему пользователю
    if conversation.user_id != current_user.id:
        abort(403)
    
    db.session.delete(conversation)
    db.session.commit()
    
    flash('Диалог успешно удален', 'success')
    return redirect(url_for('conversations.list'))

@conversations_bp.route('/<int:conversation_id>/share', methods=['POST'])
@login_required
def share(conversation_id):
    """Создает или обновляет ссылку для шаринга диалога"""
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    
    # Проверяем, принадлежит ли диалог текущему пользователю
    if conversation.user_id != current_user.id:
        abort(403)
    
    # Генерируем или обновляем токен
    token = conversation.generate_share_token()
    db.session.commit()
    
    # Формируем URL для шаринга
    share_url = url_for('conversations.shared', token=token, _external=True)
    
    return jsonify({'shareUrl': share_url})

@conversations_bp.route('/<int:conversation_id>/unshare', methods=['POST'])
@login_required
def unshare(conversation_id):
    """Отключает шаринг диалога"""
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    
    # Проверяем, принадлежит ли диалог текущему пользователю
    if conversation.user_id != current_user.id:
        abort(403)
    
    conversation.disable_sharing()
    db.session.commit()
    
    return jsonify({'success': True})

@conversations_bp.route('/shared/<token>')
def shared(token):
    """Отображает шаринговый диалог по токену"""
    conversation = db.session.query(Conversation).filter_by(share_token=token).first_or_404()
    
    if not conversation.is_shared:
        abort(404)
    
    # Получаем сообщения
    messages = conversation.messages.order_by(Message.timestamp).all()
    
    # Опционально: увеличиваем счетчик просмотров (если такая функция нужна)
    
    return render_template('chat/shared_conversation.html', 
                          conversation=conversation, 
                          messages=messages)

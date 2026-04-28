import requests
import json
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user

from database import db
from models.conversation import Conversation
from models.message import Message
from models.setting import Setting

# Создаем blueprint для взаимодействия с LLM
llm_bp = Blueprint('llm', __name__, url_prefix='/api/llm')

@llm_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    """Отправляет запрос к LLM и сохраняет ответ"""
    data = request.get_json()
    
    if not data or 'conversation_id' not in data or 'message' not in data:
        return jsonify({'error': 'Неверный формат данных'}), 400
    
    conversation_id = data['conversation_id']
    user_message = data['message']
    
    # Проверяем существование диалога и права доступа
    conversation = db.session.query(Conversation).get_or_404(conversation_id)
    if conversation.user_id != current_user.id:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    # Получаем настройки пользователя
    settings = db.session.query(Setting).filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Setting(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    
    # Получаем историю сообщений для контекста
    messages = list(conversation.messages)
    
    # Формируем контекст для LLM
    context = []
    for msg in messages:
        context.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # Добавляем новое сообщение пользователя в контекст
    context.append({
        "role": "user",
        "content": user_message
    })
    
    
    # Обновляем время последнего обновления диалога
    db.session.commit()
    
    # Настройки генерации
    generation_config = {
        "temperature": data.get('temperature', settings.temperature),
        "top_p": data.get('top_p', settings.top_p),
        "max_tokens": data.get('max_tokens', settings.max_tokens or current_app.config['LLM_DEFAULT_MAX_TOKENS'])
    }
    
    # Формируем запрос к API
    llm_api_url = current_app.config['LLM_API_URL']
    
    # Адаптируем формат запроса для text-generation-webui API
    api_request = {
        "messages": context,
        "temperature": generation_config["temperature"],
        "top_p": generation_config["top_p"],
        "max_tokens": generation_config["max_tokens"],
        "stream": False
    }
    
    try:
        # Отправляем запрос к LLM API
        response = requests.post(llm_api_url, json=api_request, timeout=60)
        
        if response.status_code != 200:
            return jsonify({
                'error': f'Ошибка LLM API: {response.status_code}',
                'details': response.text
            }), 500
        
        response_data = response.json()
        
        # Правильное извлечение ответа модели
        assistant_message = ""
        
        if isinstance(response_data, dict):
            # Проверяем разные форматы ответа
            if 'choices' in response_data and len(response_data['choices']) > 0:
                # OpenAI-совместимый формат
                choice = response_data['choices'][0]
                if 'message' in choice:
                    assistant_message = choice['message'].get('content', '')
                elif 'text' in choice:
                    assistant_message = choice['text']
            elif 'response' in response_data:
                # Простой формат с полем response
                assistant_message = response_data['response']
            elif 'content' in response_data:
                # Формат с полем content
                assistant_message = response_data['content']
            else:
                # Если структура неизвестна, берем весь JSON как строку
                assistant_message = json.dumps(response_data, ensure_ascii=False, indent=2)
        elif isinstance(response_data, list) and len(response_data) > 0:
            # Если ответ - массив, берем первый элемент
            first_item = response_data[0]
            if isinstance(first_item, dict) and 'content' in first_item:
                assistant_message = first_item['content']
            else:
                assistant_message = str(first_item)
        else:
            # Если ничего не подошло, конвертируем в строку
            assistant_message = str(response_data)
        
        # Если сообщение пустое, устанавливаем ошибку
        if not assistant_message.strip():
            assistant_message = "Извините, не удалось получить ответ от модели."
        
        # Сохраняем ответ ассистента в базу данных
        assistant_msg = Message(
            conversation_id=conversation_id,
            role='assistant',
            content=assistant_message
        )
        db.session.add(assistant_msg)
        db.session.commit()
        
        # Обновляем время последнего обновления диалога
        conversation.updated_at = assistant_msg.timestamp
        db.session.commit()
        
        # Если у диалога еще нет заголовка или заголовок по умолчанию, 
        # создаем заголовок на основе первого сообщения пользователя
        if conversation.title == 'Новый диалог' and len(messages) == 0:
            # Создаем краткий заголовок из первого сообщения
            title = user_message[:50] + ('...' if len(user_message) > 50 else '')
            conversation.title = title
            db.session.commit()
        
        return jsonify({
            'message': assistant_message,
            'message_id': assistant_msg.id
        })
    
    except requests.RequestException as e:
        return jsonify({
            'error': 'Ошибка соединения с LLM API',
            'details': str(e)
        }), 500
    
    except Exception as e:
        return jsonify({
            'error': 'Внутренняя ошибка сервера',
            'details': str(e)
        }), 500

@llm_bp.route('/models', methods=['GET'])
@login_required
def get_models():
    """Получает список доступных моделей (обертка над API LLM)"""
    # В реальном приложении здесь стоит отправить запрос к API LLM
    # для получения списка доступных моделей
    
    # Пока вернем фиксированный список
    models = [
        {
            "id": "saiga_nemo_12b",
            "name": "Saiga Nemo 12B",
            "description": "Русскоязычная модель на базе Llama 2",
        }
    ]
    
    return jsonify(models)

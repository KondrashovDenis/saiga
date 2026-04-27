import os
from datetime import datetime
from flask import Flask, render_template, request
from markupsafe import Markup
from flask_login import LoginManager, current_user

from config import Config
from database import init_db, db

app = Flask(__name__)
app.config.from_object(Config)


@app.template_filter('nl2br')
def nl2br(value):
    if isinstance(value, str):
        return Markup(value.replace('\n', '<br/>'))
    return value


init_db(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему.'


@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    return User.query.get(int(user_id))


# Blueprints
from routes.auth import auth_bp
from routes.conversations import conversations_bp
from routes.messages import messages_bp
from routes.llm import llm_bp
from routes.settings import settings_bp
from routes.telegram_auth import telegram_auth_bp
from routes.file_upload import file_upload_bp

app.register_blueprint(auth_bp)
app.register_blueprint(conversations_bp)
app.register_blueprint(messages_bp)
app.register_blueprint(llm_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(telegram_auth_bp)
app.register_blueprint(file_upload_bp)


# ──────────── context processors ────────────
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}


@app.context_processor
def inject_user():
    return {'current_user': current_user}


@app.context_processor
def inject_sidebar():
    """Список последних диалогов для sidebar — авто-инжект на все auth-страницы."""
    if not current_user.is_authenticated:
        return {'sidebar_conversations': []}
    from models.conversation import Conversation
    convs = (Conversation.query
             .filter_by(user_id=current_user.id)
             .order_by(Conversation.updated_at.desc())
             .limit(50)
             .all())
    # active_conversation_id берём из URL если в нём есть /conversations/<id>
    active_id = None
    parts = (request.path or '').strip('/').split('/')
    if len(parts) >= 2 and parts[0] == 'conversations' and parts[1].isdigit():
        active_id = int(parts[1])
    return {
        'sidebar_conversations': convs,
        'active_conversation_id': active_id,
    }


# ──────────── routes ────────────
@app.route('/')
def index():
    return render_template('index.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404,
                           error_message='Страница не найдена'), 404


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code=500,
                           error_message='Внутренняя ошибка сервера'), 500


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # gunicorn запускает прод — этот блок только для локалки
    app.run(host='0.0.0.0', port=5000, debug=False)

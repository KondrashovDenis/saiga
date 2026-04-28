import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from markupsafe import Markup
from flask_login import LoginManager, current_user

from config import Config
from database import init_db, db


# ────────────── Sentry ──────────────
# Инициализируем ДО создания Flask app — так FlaskIntegration сможет hook'нуться
# в роуты при их регистрации. Если SENTRY_DSN не задан — init no-op.
if Config.SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    sentry_sdk.init(
        dsn=Config.SENTRY_DSN,
        environment=Config.SENTRY_ENV,
        release=Config.SENTRY_RELEASE,
        integrations=[FlaskIntegration()],
        traces_sample_rate=0.1,        # 10% запросов в performance trace
        send_default_pii=False,        # не шлём username/email юзеров без явного запроса
    )


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
    return db.session.query(User).get(int(user_id))


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
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    return render_template('index.html')


@app.route('/sentry-debug')
def trigger_error():
    """Тестовая точка для проверки что Sentry ловит exceptions.
    Доступна только если SENTRY_DSN задан и FLASK_DEBUG активен."""
    if not Config.SENTRY_DSN or not app.debug:
        return 'disabled', 404
    division_by_zero = 1 / 0
    return str(division_by_zero)


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
    app.run(host='0.0.0.0', port=5000, debug=False)

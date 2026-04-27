import os
from datetime import datetime
from flask import Flask, render_template
from markupsafe import Markup
from flask_login import LoginManager, current_user

from config import Config
from database import init_db, db

# Создаем экземпляр приложения
app = Flask(__name__)
app.config.from_object(Config)

# Пользовательские фильтры Jinja2
@app.template_filter('nl2br')
def nl2br(value):
    """Заменяет переносы строк на HTML <br/>"""
    if isinstance(value, str):
        return Markup(value.replace('\n', '<br/>'))
    return value

# Инициализируем базу данных
init_db(app)

# Настройка Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Пожалуйста, войдите в систему для доступа к этой странице.'

@login_manager.user_loader
def load_user(user_id):
    from models.user import User
    return User.query.get(int(user_id))

# Регистрация маршрутов
from routes.auth import auth_bp
from routes.conversations import conversations_bp
from routes.messages import messages_bp
from routes.llm import llm_bp
from routes.settings import settings_bp
from routes.telegram_auth import telegram_auth_bp

app.register_blueprint(auth_bp)
app.register_blueprint(conversations_bp)
app.register_blueprint(messages_bp)
app.register_blueprint(llm_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(telegram_auth_bp)

# Контекстный процессор для шаблонов
@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}

@app.context_processor
def inject_user():
    return {'current_user': current_user}

# Главная страница
@app.route('/')
def index():
    return render_template('index.html')

# Обработчики ошибок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error_code=404, 
                          error_message='Страница не найдена'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', error_code=500, 
                          error_message='Внутренняя ошибка сервера'), 500

# Запуск приложения
if __name__ == '__main__':
    # Создаем таблицы, если они не существуют
    with app.app_context():
        db.create_all()
    
    # Запускаем приложение
    app.run(host='0.0.0.0', port=5000, debug=True)

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Создаем экземпляры SQLAlchemy и Migrate
db = SQLAlchemy()
migrate = Migrate()

def init_db(app):
    """
    Инициализирует базу данных для Flask-приложения
    
    Args:
        app: Экземпляр Flask-приложения
    """
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Импортируем модели, чтобы они были доступны для migrate
    from models.user import User
    from models.conversation import Conversation
    from models.message import Message
    from models.setting import Setting
    
    # Создаем таблицы при первом запуске
    with app.app_context():
        db.create_all()

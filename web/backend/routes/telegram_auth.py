import hashlib
import hmac
import time
from urllib.parse import unquote
from flask import Blueprint, request, redirect, url_for, flash, session, render_template
from flask_login import login_user, current_user
from models.user import User
from models.setting import Setting
from database import db
from config import Config

# Создаем blueprint для Telegram аутентификации
telegram_auth_bp = Blueprint('telegram_auth', __name__, url_prefix='/auth/telegram')

def verify_telegram_data(data, bot_token):
    """Проверяет подлинность данных от Telegram"""
    check_hash = data.pop('hash', '')
    data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(data.items())])
    
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    return hmac.compare_digest(calculated_hash, check_hash)

@telegram_auth_bp.route('/callback')
def telegram_callback():
    """Обработчик callback от Telegram Login Widget"""
    
    # Получаем данные от Telegram
    telegram_data = {
        'id': request.args.get('id'),
        'first_name': request.args.get('first_name', ''),
        'last_name': request.args.get('last_name', ''),
        'username': request.args.get('username', ''),
        'photo_url': request.args.get('photo_url', ''),
        'auth_date': request.args.get('auth_date'),
        'hash': request.args.get('hash')
    }
    
    # Удаляем None значения
    telegram_data = {k: unquote(v) if v else '' for k, v in telegram_data.items() if v is not None}
    
    if not telegram_data.get('id') or not telegram_data.get('hash'):
        flash('Ошибка аутентификации Telegram', 'danger')
        return redirect(url_for('auth.login'))
    
    # Проверяем время (данные должны быть не старше 1 часа)
    auth_date = int(telegram_data.get('auth_date', 0))
    if time.time() - auth_date > 3600:
        flash('Данные аутентификации устарели', 'danger')
        return redirect(url_for('auth.login'))
    
    # Верификация данных (в продакшене нужен реальный токен бота)
    # bot_token = Config.TELEGRAM_BOT_TOKEN
    # if not verify_telegram_data(telegram_data.copy(), bot_token):
    #     flash('Неверные данные аутентификации', 'danger')
    #     return redirect(url_for('auth.login'))
    
    telegram_id = int(telegram_data['id'])
    
    # Ищем пользователя по telegram_id
    user = User.find_by_telegram_id(telegram_id)
    
    if user:
        # Обновляем данные пользователя
        user.telegram_username = telegram_data.get('username')
        user.first_name = telegram_data.get('first_name')
        user.last_name = telegram_data.get('last_name')
        user.last_activity = db.func.now()
        
        db.session.commit()
        
        # Авторизуем пользователя
        login_user(user, remember=True)
        flash(f'Добро пожаловать, {user.display_name}!', 'success')
        
        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('index'))
    
    else:
        # Пользователь не найден в системе
        # Сохраняем данные в сессии для регистрации
        session['telegram_data'] = telegram_data
        flash('Ваш Telegram аккаунт не связан с системой. Создайте аккаунт или свяжите существующий.', 'info')
        return redirect(url_for('telegram_auth.link_account'))

@telegram_auth_bp.route('/link')
def link_account():
    """Страница связывания Telegram аккаунта"""
    telegram_data = session.get('telegram_data')
    if not telegram_data:
        flash('Данные Telegram не найдены. Повторите авторизацию.', 'danger')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/telegram_link.html', telegram_data=telegram_data)

@telegram_auth_bp.route('/create', methods=['POST'])
def create_account():
    """Создание нового аккаунта через Telegram"""
    telegram_data = session.get('telegram_data')
    if not telegram_data:
        flash('Данные Telegram не найдены. Повторите авторизацию.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Создаем нового пользователя
    user = User(
        telegram_id=int(telegram_data['id']),
        telegram_username=telegram_data.get('username'),
        first_name=telegram_data.get('first_name'),
        last_name=telegram_data.get('last_name')
    )
    user.auth_method = 'telegram'
    
    db.session.add(user)
    db.session.commit()
    
    # Создаем настройки по умолчанию
    setting = Setting(user_id=user.id)
    db.session.add(setting)
    db.session.commit()
    
    # Очищаем сессию
    session.pop('telegram_data', None)
    
    # Авторизуем пользователя
    login_user(user, remember=True)
    flash(f'Аккаунт создан! Добро пожаловать, {user.display_name}!', 'success')
    
    return redirect(url_for('index'))

@telegram_auth_bp.route('/link-existing', methods=['POST'])
def link_existing():
    """Связывание Telegram с существующим аккаунтом"""
    telegram_data = session.get('telegram_data')
    if not telegram_data:
        flash('Данные Telegram не найдены. Повторите авторизацию.', 'danger')
        return redirect(url_for('auth.login'))
    
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        flash('Введите email и пароль', 'danger')
        return redirect(url_for('telegram_auth.link_account'))
    
    # Ищем пользователя по email
    user = User.find_by_email(email)
    if not user or not user.check_password(password):
        flash('Неверный email или пароль', 'danger')
        return redirect(url_for('telegram_auth.link_account'))
    
    # Проверяем, не привязан ли уже другой Telegram
    if user.telegram_id and user.telegram_id != int(telegram_data['id']):
        flash('К этому аккаунту уже привязан другой Telegram', 'danger')
        return redirect(url_for('telegram_auth.link_account'))
    
    # Связываем аккаунты
    user.link_telegram(
        telegram_id=int(telegram_data['id']),
        telegram_username=telegram_data.get('username'),
        first_name=telegram_data.get('first_name'),
        last_name=telegram_data.get('last_name')
    )
    
    db.session.commit()
    
    # Очищаем сессию
    session.pop('telegram_data', None)
    
    # Авторизуем пользователя
    login_user(user, remember=True)
    flash(f'Telegram аккаунт успешно привязан! Добро пожаловать, {user.display_name}!', 'success')
    
    return redirect(url_for('index'))

@telegram_auth_bp.route('/unlink', methods=['POST'])
def unlink_account():
    """Отвязывание Telegram аккаунта"""
    if not current_user.is_authenticated:
        flash('Необходимо войти в систему', 'danger')
        return redirect(url_for('auth.login'))
    
    if not current_user.can_login_with_password:
        flash('Нельзя отвязать Telegram - это единственный способ входа. Сначала установите пароль.', 'danger')
        return redirect(url_for('settings.user_settings'))
    
    if current_user.unlink_telegram():
        db.session.commit()
        flash('Telegram аккаунт отвязан', 'success')
    else:
        flash('Ошибка отвязывания аккаунта', 'danger')
    
    return redirect(url_for('settings.user_settings'))

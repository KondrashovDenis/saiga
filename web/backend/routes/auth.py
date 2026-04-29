from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from database import db
from extensions import limiter
from models.user import User
from models.setting import Setting

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def _is_safe_redirect(target: str) -> bool:
    """True только если target — относительный путь на этот же origin.

    Блокирует:
      - None / пустая строка
      - абсолютные URL (https://evil.com/...)
      - protocol-relative (//evil.com/...) ← это пропускала старая версия
      - схемы (javascript:, data:, file:)
    """
    if not target or not target.startswith('/'):
        return False
    if target.startswith('//') or target.startswith('/\\'):
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc


# Формы для регистрации и входа
class RegistrationForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[
        DataRequired(),
        Length(min=3, max=64)
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(),
        Length(max=120)
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(),
        Length(min=8)
    ])
    password2 = PasswordField('Повторите пароль', validators=[
        DataRequired(),
        EqualTo('password', message='Пароли должны совпадать')
    ])
    submit = SubmitField('Зарегистрироваться')

    def validate_username(self, username):
        user = db.session.query(User).filter_by(username=username.data).first()
        if user is not None:
            # Намеренно generic-сообщение — не палим username enumeration.
            raise ValidationError('Эти учётные данные уже используются.')

    def validate_email(self, email):
        user = db.session.query(User).filter_by(email=email.data).first()
        if user is not None:
            # Намеренно generic-сообщение — не палим email enumeration.
            raise ValidationError('Эти учётные данные уже используются.')


class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    remember_me = BooleanField('Запомнить меня')
    submit = SubmitField('Войти')


# Маршруты для аутентификации
@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour; 10 per day", methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # ВАЖНО: пароль ставим через set_password() — это вызывает
        # werkzeug.security.generate_password_hash (PBKDF2-SHA256). Прямое
        # присваивание password=... как kwarg в SA-конструкторе бросило бы
        # TypeError, плюс хеширование не произошло бы.
        user = User(
            username=form.username.data,
            email=form.email.data,
            auth_method='email',
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # Создаем настройки по умолчанию для пользователя
        setting = Setting(user_id=user.id)
        db.session.add(setting)
        db.session.commit()

        flash('Вы успешно зарегистрировались! Теперь вы можете войти.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute; 30 per hour", methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter_by(username=form.username.data).first()

        if user is None or not user.check_password(form.password.data):
            flash('Неверное имя пользователя или пароль', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=form.remember_me.data)

        # Защита от open redirect: проверяем что next — относительный путь
        # на этом же origin. Старая проверка startswith('/') пропускала //evil.com.
        next_page = request.args.get('next')
        if not _is_safe_redirect(next_page):
            next_page = url_for('index')

        flash(f'Добро пожаловать, {user.username}!', 'success')
        return redirect(next_page)

    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

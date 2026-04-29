from urllib.parse import urlparse

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError

from database import db
from extensions import limiter
from models.user import User
from models.setting import Setting
from utils.email_service import (
    make_verify_token,
    parse_verify_token,
    send_verify_email,
    is_smtp_configured,
)

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


class ResendVerifyForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField('Отправить ещё раз')


def _send_verify_email_for_user(user: User) -> bool:
    """Сгенерировать токен и отправить confirm-link юзеру."""
    token = make_verify_token(user.id, user.email)
    verify_url = url_for('auth.verify_email', token=token, _external=True)
    return send_verify_email(user.email, user.username or user.email, verify_url)


# Маршруты для аутентификации
@auth_bp.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour; 10 per day", methods=['POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    form = RegistrationForm()
    if form.validate_on_submit():
        # ВАЖНО: пароль ставим через set_password() — это вызывает
        # werkzeug.security.generate_password_hash (PBKDF2-SHA256).
        user = User(
            username=form.username.data,
            email=form.email.data,
            auth_method='email',
            email_verified=False,   # подтвердит через email-link
        )
        user.set_password(form.password.data)

        db.session.add(user)
        db.session.commit()

        # Создаем настройки по умолчанию для пользователя
        setting = Setting(user_id=user.id)
        db.session.add(setting)
        db.session.commit()

        # Отправляем confirm-email. Если SMTP не настроен — логируется warning,
        # юзер увидит "проверь почту", но фактически не сможет войти, пока админ
        # не настроит SMTP или не подтвердит вручную.
        sent = _send_verify_email_for_user(user)
        if sent:
            flash(f'Регистрация создана. Подтверди email — мы прислали ссылку '
                  f'на {user.email}. Ссылка живёт 24 часа.', 'success')
        else:
            flash('Регистрация создана, но письмо отправить не удалось. '
                  'Попробуй "Прислать ещё раз" или напиши админу.', 'warning')
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

        # Email верификация для password-юзеров. TG-only юзеры не блокируются.
        if user.needs_email_verification:
            flash('Сначала подтверди email — мы прислали ссылку при регистрации. '
                  'Не пришло письмо? Запроси новое.', 'warning')
            return redirect(url_for('auth.resend_verify'))

        login_user(user, remember=form.remember_me.data)

        # Защита от open redirect.
        next_page = request.args.get('next')
        if not _is_safe_redirect(next_page):
            next_page = url_for('index')

        flash(f'Добро пожаловать, {user.username}!', 'success')
        return redirect(next_page)

    return render_template('auth/login.html', form=form)


@auth_bp.route('/verify/<token>')
@limiter.limit("20 per hour")
def verify_email(token):
    """Подтверждение email по signed-token. Ссылка из письма."""
    user_id, email = parse_verify_token(token)
    if user_id is None:
        flash('Ссылка недействительна или истекла. Запроси новое письмо.', 'danger')
        return redirect(url_for('auth.resend_verify'))

    user = db.session.query(User).get(user_id)
    if user is None or user.email != email:
        # Email сменился после генерации токена — токен невалиден.
        flash('Ссылка не подходит к этому аккаунту.', 'danger')
        return redirect(url_for('auth.login'))

    if user.email_verified:
        flash('Email уже подтверждён, можно входить.', 'info')
        return redirect(url_for('auth.login'))

    user.email_verified = True
    db.session.commit()
    flash('Email подтверждён. Теперь можно войти.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/resend-verify', methods=['GET', 'POST'])
@limiter.limit("3 per hour")
def resend_verify():
    """Повторная отправка confirm-email. Защита от user enumeration —
    всегда возвращаем 'отправлено', даже если email не существует."""
    form = ResendVerifyForm()
    if form.validate_on_submit():
        user = db.session.query(User).filter_by(email=form.email.data).first()
        # Шлём только если есть юзер с password-auth и не подтверждён.
        if user and user.password_hash and not user.email_verified:
            _send_verify_email_for_user(user)
        # Generic-ответ независимо от existence — не палим accounts.
        flash('Если этот email есть в системе и не подтверждён — мы прислали ссылку.',
              'info')
        return redirect(url_for('auth.login'))
    return render_template('auth/resend_verify.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))

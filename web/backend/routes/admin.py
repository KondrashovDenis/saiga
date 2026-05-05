"""Admin-страницы: управление юзерами.

Доступ: только User.is_admin = TRUE. Все endpoint'ы проверяют через
@admin_required (внутри декоратор делает abort(403) для не-админа).

Доступные действия:
- /admin/users         — список юзеров (GET)
- /admin/users/<id>/toggle-admin   — toggle is_admin (POST)
- /admin/users/<id>/toggle-verified — toggle email_verified (POST)
- /admin/users/<id>/reset-password — сгенерить новый пароль, показать админу (POST)
- /admin/users/<id>/send-reset-email — послать reset-link юзеру через email (POST)
- /admin/users/<id>/delete         — удалить юзера + все его данные (POST)

Все mutating-actions редиректят обратно на /admin/users с flash.
Audit-trail — logger.info, потом подцепится в Sentry breadcrumbs.
"""
from functools import wraps
import logging
import secrets
import string

from flask import Blueprint, render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from sqlalchemy import desc

from database import db
from extensions import limiter
from models.user import User
from utils.email_service import send_password_reset_email, make_password_reset_token


logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Декоратор: 403 если current_user не админ. Применяется ПОСЛЕ login_required."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapper


def _generate_random_password(length: int = 16) -> str:
    """URL-safe-ish случайный пароль. Без спецсимволов которые ломаются в URL."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


@admin_bp.route('/users')
@login_required
@admin_required
def users_list():
    users = db.session.query(User).order_by(desc(User.created_at)).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
@limiter.limit("30 per hour")
def toggle_admin(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash('Нельзя снять админа с самого себя — попроси другого админа.', 'warning')
        return redirect(url_for('admin.users_list'))
    user.is_admin = not user.is_admin
    db.session.commit()
    logger.info("admin %s toggled is_admin for user_id=%s → %s",
                current_user.username, user.id, user.is_admin)
    flash(f'is_admin для {user.display_name}: {user.is_admin}', 'success')
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/users/<int:user_id>/toggle-verified', methods=['POST'])
@login_required
@admin_required
@limiter.limit("30 per hour")
def toggle_verified(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    user.email_verified = not user.email_verified
    db.session.commit()
    logger.info("admin %s toggled email_verified for user_id=%s → %s",
                current_user.username, user.id, user.email_verified)
    flash(f'email_verified для {user.display_name}: {user.email_verified}', 'success')
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@admin_required
@limiter.limit("20 per hour")
def reset_password_inline(user_id):
    """Сгенерить новый случайный пароль и показать админу через flash.

    Альтернатива send-reset-email если у юзера нет рабочего email или
    нужно срочно. Юзер потом сам поменяет в Settings.
    """
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    new_pwd = _generate_random_password(16)
    user.set_password(new_pwd)
    db.session.commit()
    logger.info("admin %s reset password (inline) for user_id=%s", current_user.username, user.id)
    flash(f'Новый пароль для {user.display_name}: {new_pwd} — скопируй сейчас, '
          f'обновление страницы скроет.', 'warning')
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/users/<int:user_id>/send-reset-email', methods=['POST'])
@login_required
@admin_required
@limiter.limit("20 per hour")
def send_reset_email(user_id):
    """Послать юзеру email со ссылкой для сброса пароля (если у него есть email)."""
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if not user.email:
        flash(f'У {user.display_name} нет email — нельзя послать reset-ссылку. '
              f'Используй "Reset inline" чтобы сгенерить пароль.', 'warning')
        return redirect(url_for('admin.users_list'))

    token = make_password_reset_token(user.id, user.password_hash or "")
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    sent = send_password_reset_email(user.email, user.username or user.email, reset_url)
    if sent:
        logger.info("admin %s sent password-reset email to user_id=%s", current_user.username, user.id)
        flash(f'Reset-ссылка отправлена на {user.email} (живёт 1 час).', 'success')
    else:
        flash(f'Не удалось отправить email на {user.email} (SMTP не настроен или fail). '
              f'См. логи web-app.', 'danger')
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
@limiter.limit("10 per hour")
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user.id:
        flash('Нельзя удалить самого себя.', 'danger')
        return redirect(url_for('admin.users_list'))

    # Подтверждение через POST-параметр (форма пошлёт confirm=username)
    confirm = request.form.get('confirm', '').strip()
    # Для TG-only юзеров (нет username и email) явный префикс tg-{id} — чтобы
    # админ понимал что вводит, а не просто число.
    expected = user.username or user.email or f"tg-{user.id}"
    if confirm != expected:
        flash(f'Подтверждение не совпало. Жду точное "{expected}".', 'danger')
        return redirect(url_for('admin.users_list'))

    display = user.display_name
    db.session.delete(user)  # cascade удалит conversations/messages/settings/tokens
    db.session.commit()
    logger.warning("admin %s DELETED user_id=%s (%s)", current_user.username, user_id, display)
    flash(f'Юзер {display} удалён со всеми диалогами.', 'info')
    return redirect(url_for('admin.users_list'))

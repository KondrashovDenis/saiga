from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, FloatField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Email, NumberRange

from database import db
from models.setting import Setting

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

class UserSettingsForm(FlaskForm):
    ui_theme = SelectField('Тема интерфейса', choices=[
        ('auto', 'Автоматическая'),
        ('light', 'Светлая'),
        ('dark', 'Темная')
    ])
    temperature = FloatField('Temperature', validators=[
        NumberRange(min=0.1, max=1.0, message='Значение должно быть от 0.1 до 1.0')
    ])
    top_p = FloatField('Top P', validators=[
        NumberRange(min=0.1, max=1.0, message='Значение должно быть от 0.1 до 1.0')
    ])
    message_animations = BooleanField('Анимации сообщений')
    auto_scroll = BooleanField('Автоматическая прокрутка')
    show_timestamps = BooleanField('Показывать время сообщений')
    show_quick_replies = BooleanField('Показывать быстрые ответы')
    enable_reactions = BooleanField('Включить реакции на сообщения')
    markdown_support = BooleanField('Поддержка Markdown')
    submit = SubmitField('Сохранить настройки')

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def user_settings():
    """Страница настроек пользователя"""
    settings = Setting.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Setting(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    
    form = UserSettingsForm(obj=settings)
    
    if form.validate_on_submit():
        form.populate_obj(settings)
        db.session.commit()
        
        flash('Настройки успешно сохранены', 'success')
        return redirect(url_for('settings.user_settings'))
    
    return render_template('settings/user_settings.html', form=form)

@settings_bp.route('/theme', methods=['POST'])
@login_required
def save_theme():
    """API для сохранения темы пользователя"""
    data = request.get_json()
    if not data or 'theme' not in data:
        return jsonify({'error': 'Неверный формат данных'}), 400
    
    theme = data['theme']
    if theme not in ['light', 'dark', 'auto']:
        return jsonify({'error': 'Неверная тема'}), 400
    
    settings = Setting.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Setting(user_id=current_user.id)
        db.session.add(settings)
    
    settings.ui_theme = theme
    db.session.commit()
    
    return jsonify({'success': True})

@settings_bp.route('/api', methods=['GET'])
@login_required
def get_user_settings_api():
    """API для получения настроек пользователя"""
    settings = Setting.query.filter_by(user_id=current_user.id).first()
    if not settings:
        settings = Setting(user_id=current_user.id)
        db.session.add(settings)
        db.session.commit()
    
    return jsonify(settings.to_dict())

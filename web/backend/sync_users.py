#!/usr/bin/env python3
"""
Скрипт синхронизации пользователей между Telegram ботом и веб-версией
"""
import sqlite3
from datetime import datetime
from app import app
from database import db
from models.user import User

def sync_telegram_users_to_web():
    """Синхронизирует пользователей из ТГ-бота в веб-версию"""
    
    # Подключаемся к БД Telegram бота
    tg_conn = sqlite3.connect('/tmp/saiga_bot.db')
    tg_cursor = tg_conn.cursor()
    
    # Получаем всех пользователей из ТГ-бота
    tg_cursor.execute("""
        SELECT id, telegram_id, telegram_username, first_name, last_name, 
               language_code, created_at, last_activity, is_admin, is_active
        FROM users
    """)
    
    tg_users = tg_cursor.fetchall()
    print(f"Найдено {len(tg_users)} пользователей в Telegram боте")
    
    with app.app_context():
        synced_count = 0
        updated_count = 0
        
        for tg_user in tg_users:
            (tg_id, telegram_id, telegram_username, first_name, last_name, 
             language_code, created_at, last_activity, is_admin, is_active) = tg_user
            
            # Проверяем, есть ли уже пользователь с таким telegram_id
            existing_user = User.find_by_telegram_id(telegram_id)
            
            if existing_user:
                # Обновляем существующего пользователя
                existing_user.telegram_username = telegram_username
                existing_user.first_name = first_name
                existing_user.last_name = last_name
                existing_user.language_code = language_code or 'ru'
                existing_user.last_activity = datetime.fromisoformat(last_activity) if last_activity else datetime.utcnow()
                existing_user.is_admin = bool(is_admin)
                existing_user.is_active = bool(is_active)
                
                # Обновляем метод аутентификации
                if existing_user.auth_method == 'email':
                    existing_user.auth_method = 'both'
                elif existing_user.auth_method != 'both':
                    existing_user.auth_method = 'telegram'
                
                updated_count += 1
                print(f"Обновлен пользователь: {existing_user.display_name}")
            else:
                # Создаем нового пользователя
                new_user = User(
                    telegram_id=telegram_id,
                    telegram_username=telegram_username,
                    first_name=first_name,
                    last_name=last_name,
                    language_code=language_code or 'ru',
                    is_admin=bool(is_admin),
                    is_active=bool(is_active)
                )
                new_user.created_at = datetime.fromisoformat(created_at) if created_at else datetime.utcnow()
                new_user.last_activity = datetime.fromisoformat(last_activity) if last_activity else datetime.utcnow()
                new_user.auth_method = 'telegram'
                
                db.session.add(new_user)
                synced_count += 1
                print(f"Создан новый пользователь: {new_user.display_name}")
        
        # Сохраняем изменения
        db.session.commit()
        
        print(f"\nСинхронизация завершена:")
        print(f"- Создано новых пользователей: {synced_count}")
        print(f"- Обновлено существующих: {updated_count}")
    
    tg_conn.close()

if __name__ == '__main__':
    sync_telegram_users_to_web()

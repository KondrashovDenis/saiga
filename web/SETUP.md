# Инструкция по запуску Saiga Web App

## 1. Предварительная подготовка

### 1.1. Проверка структуры проекта
cd ~/saiga-web-app
ls -la

Убедитесь, что структура проекта выглядит примерно так:
- backend/ (директория с кодом приложения)
- docker/ (директория с файлами Docker)
- README.md (общее описание проекта)
- SETUP.md (этот файл)
### 1.2. Создание SSL-сертификата для домена
sudo certbot certonly --nginx -d saiga.denciaopin.com

## 2. Сборка и запуск приложения

### 2.1. Сборка Docker-образа
cd ~/saiga-web-app
docker build -t saiga-web-app:latest backend/

### 2.2. Запуск контейнеров
cd ~/saiga-web-app/docker
docker-compose up -d
### 2.3. Проверка статуса контейнеров
docker ps | grep saiga

## 3. Настройка Nginx-proxy

### 3.1. Проверка конфигурации Nginx
cd ~/nginx-proxy
docker-compose exec nginx-proxy nginx -t

### 3.2. Применение конфигурации Nginx
cd ~/nginx-proxy
docker-compose exec nginx-proxy nginx -s reload
### 3.3. Проверка доступности приложения
curl -I https://saiga.denciaopin.com

## 4. Создание первого администратора

После запуска приложения, зарегистрируйте первого пользователя через веб-интерфейс, затем выполните:

docker exec -it saiga-web-app flask shell

И внутри оболочки Python:
from models.user import User
from database import db
user = User.query.filter_by(username='your_username').first()
user.is_admin = True
db.session.commit()
exit()
## 5. Устранение неполадок

### 5.1. Проверка логов приложения
docker logs saiga-web-app

### 5.2. Проверка логов Nginx-proxy
cd ~/nginx-proxy
docker-compose logs nginx-proxy

### 5.3. Перезапуск приложения
cd ~/saiga-web-app/docker
docker-compose restart

#!/bin/bash

# Директория для бэкапов
BACKUP_DIR="/root/backups/saiga-web-app"
mkdir -p $BACKUP_DIR

# Дата для имени файла
DATE=$(date +"%Y-%m-%d_%H-%M-%S")

# Копирование данных
docker exec saiga-web-app tar -czf - /data | cat > $BACKUP_DIR/saiga_data_$DATE.tar.gz

# Удаление старых бэкапов (оставляем только последние 7)
ls -tp $BACKUP_DIR/saiga_data_*.tar.gz | grep -v '/$' | tail -n +8 | xargs -I {} rm -- {}

echo "Резервное копирование завершено: $BACKUP_DIR/saiga_data_$DATE.tar.gz"

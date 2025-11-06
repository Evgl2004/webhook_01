#!/bin/bash

echo "Начало установки... Starting deployment..."

# Создание папки для логов
mkdir -p logs

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo "Ошибка: .env файл не найден! Error: .env file not found!"
    echo "Пожалуйста создайте .env файл из файла .env.example  Please create .env file from .env.example"
    exit 1
fi

# Запуск сервисов

# Останавливаем предыдущие контейнеры
echo "Останавливаем предыдущие контейнеры... Stopping previous containers..."
docker-compose down

# Запускаем базу данных и redis
echo "Запускаем базу данных и redis... Starting database and redis..."
docker-compose up -d db redis

# Ждем готовности БД
echo "Ждем готовности базы данных... Waiting for database to be ready..."
sleep 10

# Запускаем миграции
echo "Запускаем миграции... Running database migrations..."
docker-compose up migrate

# Проверяем успешность миграций
if [ $? -ne 0 ]; then
    echo "Ошибка: Не удалось выполнить миграцию базы данных! Error: Database migrations failed!"
    exit 1
fi

# Запускаем основные сервисы
echo "Запускаем основные сервисы... Starting main services..."
docker-compose up -d app celery celery-beat nginx

# Предыдущая версия, где был запуск всего и сразу, без отдельных миграций
# docker-compose up --build -d

# Ждем и проверяем статус
sleep 10
echo "Проверяем статус... Checking services status..."
docker-compose ps

echo "Установка завершена! Deployment completed!"
echo "Приложение запускается... Application is starting..."
echo "Для проверки статуса: Check status with: docker compose ps"
echo "Для просмотра статуса: View logs with: docker compose logs -f"
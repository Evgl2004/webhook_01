#!/bin/bash

echo -e "\n Начало установки... \n Starting deployment... \n"

# Создание папки для логов
echo -e "\n Создание папки для логов... \n Creating a folder for logs... \n"
mkdir -p logs

# Проверка наличия .env файла
if [ ! -f .env ]; then
    echo -e "\n Ошибка: .env файл не найден! \n Error: .env file not found! "
    echo -e "\n Пожалуйста создайте .env файл из файла .env.sample \n Please create .env file from .env.sample \n"
    exit 1
fi

# Запуск сервисов

# Останавливаем предыдущие контейнеры
echo -e "\n Останавливаем предыдущие контейнеры... \n Stopping previous containers... \n"
docker compose down

# Запускаем базу данных и redis
echo -e "\n Запускаем базу данных и redis... \n Starting database and redis... \n"
docker compose up -d db redis

# Ждем готовности БД
echo -e "\n Ждем готовности базы данных 20с... \n Waiting for database to be ready 20s... \n"
sleep 20

# Запускаем миграции
echo -e "\n Запускаем миграции... \n Running database migrations... \n"
docker compose up migrate

# Проверяем успешность миграций
if [ $? -ne 0 ]; then
    echo -e "\n Ошибка: Не удалось выполнить миграцию базы данных! \n Error: Database migrations failed! \n"
    exit 1
fi

# Запускаем основные сервисы
echo -e "\n Запускаем основные сервисы... \n Starting main services... \n"
docker compose up -d app celery celery-beat nginx

# Предыдущая версия, где был запуск всего и сразу, без отдельных миграций
# docker compose up --build -d

# Ждем и проверяем статус
echo -e "\n Ждём 20с и проверяем статус... \n Wait 20s and checking services status... \n"
sleep 20
docker compose ps

echo -e "\n Установка завершена! \n Deployment completed!"
echo -e "\n Для проверки статуса: \n Check status with: \n docker compose ps"
echo -e "\n Для просмотра статуса: \n View logs with: \n docker compose logs -f"
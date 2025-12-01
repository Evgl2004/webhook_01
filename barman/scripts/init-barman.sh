#!/bin/bash
set -e

echo "$(date): Начало инициализации Barman..."

# СОЗДАЕМ КОНФИГУРАЦИОННЫЙ ФАЙЛ DB.CONF ДИНАМИЧЕСКИ
echo "Создание db.conf из переменных окружения..."
cat > /etc/barman/conf.d/db.conf << EOF
[db]
description = "Сервер СУБД PostgreSQL приложения журналирования уведомлений"
conninfo = host=${POSTGRES_HOST} user=${BARMAN_USER} password=${BARMAN_PASSWORD} dbname=${POSTGRES_DB}
streaming_conninfo = host=${POSTGRES_HOST} user=${STREAMING_BARMAN_USER} password=${STREAMING_BARMAN_PASSWORD} dbname=${POSTGRES_DB}
backup_method = postgres
streaming_archiver = on
slot_name = barman_slot
archiver = off
retention_policy = RECOVERY WINDOW OF 2 WEEKS
minimum_redundancy = 2
EOF

# Проверяем что все переменные установлены
required_vars=("BARMAN_USER" "BARMAN_PASSWORD" "STREAMING_BARMAN_USER" "STREAMING_BARMAN_PASSWORD" "POSTGRES_HOST" "POSTGRES_PORT" "POSTGRES_DB")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "✗ ОШИБКА: Не установлена переменная $var"
        exit 1
    fi
done

# Ждем когда БД будет готова
until pg_isready -h db -p 5432 -U barman; do
  echo "Ожидаем ответа от базы данных..."
  sleep 2
done

echo "База данных готова. Выполняем настройку Barman..."

# Создаем слот репликации если не существует
if barman receive-wal --create-slot db >/dev/null 2>&1; then
    echo "Создание слота репликации..."
    barman receive-wal --create-slot db || echo "Настройка слота репликации завершена"
else
    echo "Слот репликации существует"
fi

echo "Проверка receive-wal..."

# Убиваем старые процессы receive-wal если есть
pkill -f "barman receive-wal" || true
sleep 2

# Запускаем receive-wal
echo "Запуск receive-wal..."
barman receive-wal db > /var/log/barman/receive-wal.log 2>&1 &

# Ждем и проверяем запуск
sleep 2
if ps aux | grep "[b]arman receive-wal" > /dev/null; then
    echo "✓ receive-wal запущен"
else
    echo "✗ receive-wal не запустился"
fi

# Запускаем cron в фоновом режиме
echo "Запуск процесса Barman cron в фоновом режиме..."
barman cron > /var/log/barman/cron.log 2>&1 &
sleep 2

echo "$(date): Инициализация Barman успешно завершена"
sleep 2

# Проверяем конфигурацию
echo "Проверка конфигурации Barman:"
barman check db &

# Используем sleep infinity вместо бесконечного цикла
echo "Контейнер Barman останется активным с бесконечностью сна..."
exec sleep infinity
#!/bin/bash
set -e
echo "$(date '+%Y-%m-%d %H:%M:%S'): [Init] Начало инициализации от root..."

# ОТЛАДОЧНЫЙ ВЫВОД - проверка переменных
echo "=== Проверка переменных окружения ==="
echo "POSTGRES_HOST: ${POSTGRES_HOST:-NOT_SET}"
echo "POSTGRES_PORT: ${POSTGRES_PORT:-NOT_SET}"
echo "POSTGRES_DB: ${POSTGRES_DB:-NOT_SET}"
echo "BARMAN_USER: ${BARMAN_USER:-NOT_SET}"
echo "STREAMING_BARMAN_USER: ${STREAMING_BARMAN_USER:-NOT_SET}"
echo "====================================="

# Проверяем что все переменные установлены
required_vars=("BARMAN_USER" "BARMAN_PASSWORD" "STREAMING_BARMAN_USER" "STREAMING_BARMAN_PASSWORD" "POSTGRES_HOST" "POSTGRES_PORT" "POSTGRES_DB")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "✗ ОШИБКА: Не установлена переменная $var"
        exit 1
    fi
done

# 1. НАСТРОЙКА ПРАВ ДЛЯ ЛОГОВ И ДАННЫХ
echo "Настройка прав для каталогов..."
chown -R barman:barman /var/log/barman /var/lib/barman
chmod 755 /var/log/barman /var/lib/barman

# 2. СОЗДАНИЕ КОНФИГА DB.CONF (от root, но владелец barman)
echo "Создание db.conf..."
cat > /etc/barman/conf.d/db.conf << EOF
[db]
description = "Сервер СУБД PostgreSQL"
conninfo = host=${POSTGRES_HOST} user=${BARMAN_USER} password=${BARMAN_PASSWORD} dbname=${POSTGRES_DB}
streaming_conninfo = host=${POSTGRES_HOST} user=${STREAMING_BARMAN_USER} password=${STREAMING_BARMAN_PASSWORD} dbname=${POSTGRES_DB}
backup_method = postgres
streaming_archiver = on
slot_name = barman_slot
archiver = off
retention_policy = REDUNDANCY 7
minimum_redundancy = 7
EOF
#chown barman:barman /etc/barman/conf.d/db.conf

# ============================================================================
# ЗАПУСК СИСТЕМНОГО CRON (требует root)
# ============================================================================

echo "Настройка планировщика задач cron..."

# 3. ОСТАНОВИТЬ старый фоновый цикл barman cron (если он запущен от предыдущих версий скрипта)
# Ищем и завершаем процессы, которые являются нашим shell-циклом для barman cron
echo "Остановка старого фонового цикла barman cron (если есть)..."
pkill -f "bash.*while true.*barman cron" 2>/dev/null || true
sleep 1

# 4. ЗАПУСТИТЬ системный демон cron
# Теперь мы устанавливаем пакет 'cron' в Dockerfile, поэтому демон доступен
echo "Запуск системного демона cron..."

# КРИТИЧНО: Создаем директорию для PID-файла, если её нет
mkdir -p /var/run/cron
chmod 755 /var/run/cron
cron

# Даем cron время запуститься и зачитать начальную конфигурацию
sleep 2


# 5. АКТИВИРОВАТЬ стандартную задачу Barman и наши кастомные задачи
# Файлы конфигурации будут смонтированы в контейнер через docker-compose.yml:
# - /etc/cron.d/barman (стандартная задача раз в минуту для 'barman cron')
# - /etc/cron.d/barman-custom (наши задачи для backup, check, delete)
echo "Активация cron-задач Barman..."
echo "✓ Задача 'barman cron' будет выполняться ежеминутно из /etc/cron.d/barman"
echo "✓ Пользовательские задачи (резервное копирование, проверка, очистка) загружены из /etc/cron.d/barman-custom"

# 6. ДОПОЛНИТЕЛЬНО: Перенаправим логи cron демона в отдельный файл для удобства
# (Опционально, но рекомендуется для удобства отладки)
CRON_LOG="/var/log/barman/cron_daemon.log"
echo "Логи системного cron будут направлены в $CRON_LOG"
# Это можно сделать, добавив в конец файла /etc/cron.d/barman-custom строку:
# '> /var/log/barman/cron_daemon.log 2>&1' к каждой задаче, но проще настроить в самой задаче.

# 7. КРАТКАЯ ПРОВЕРКА: Покажем, какие cron-задачи загружены
echo "--- Список активных задач cron для Barman ---"
cat /etc/cron.d/barman 2>/dev/null | grep -v '^#' || echo "Файл /etc/cron.d/barman не найден или пуст"
cat /etc/cron.d/barman-custom 2>/dev/null | grep -v '^#' || echo "Файл /etc/cron.d/barman-custom не найден или пуст"
echo "--- Конец списка ---"

# 8. ПЕРЕКЛЮЧЕНИЕ НА ПОЛЬЗОВАТЕЛЯ BARMAN И ЗАПУСК ОСНОВНОГО СКРИПТА
echo "Переключение на пользователя 'barman' и запуск основного entrypoint..."
exec su -p barman -c "/opt/barman-scripts/entrypoint.sh"
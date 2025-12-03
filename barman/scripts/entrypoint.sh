#!/bin/bash
set -e
# Этот скрипт выполняется ОТ пользователя BARMAN (через USER в Dockerfile)

# Устанавливаем корректный часовой пояс для всех процессов
export TZ=Asia/Yekaterinburg
export LC_TIME=C.UTF-8

echo "$(date '+%Y-%m-%d %H:%M:%S'): [Barman] Запуск основных процессов..."

# Проверяем, что база данных доступна (теперь от пользователя barman)
until pg_isready -h db -p 5432 -U barman; do
  echo "Ожидаем ответа от базы данных..."
  sleep 2
done

echo "База данных готова. Выполняем финальную настройку Barman..."

# Создаем слот репликации если не существует
if barman receive-wal --create-slot db >/dev/null 2>&1; then
    echo "Создание слота репликации..."
    barman receive-wal --create-slot db || echo "Настройка слота репликации завершена"
else
    echo "Слот репликации существует"
fi

echo "Проверка receive-wal..."

# Запускаем receive-wal только если он ещё не работает
if ps aux | grep -q "[b]arman receive-wal"; then
    echo "✓ receive-wal уже работает"
else
    echo "Запуск receive-wal..."
    barman receive-wal db >> /var/log/barman/receive-wal.log 2>&1 &

    # Даём время на стабильный запуск
    sleep 5

    if ps aux | grep -q "[b]arman receive-wal"; then
        echo "✓ receive-wal успешно запущен"
    else
        echo "⚠ receive-wal требует дополнительной проверки (см. /var/log/barman/receive-wal.log)"
    fi
fi

# Демон cron уже запущен скриптом инициализации от root.
# Теперь просто ждём, пока он будет выполнять задачи от barman.
echo "Система Barman готова. Логи cron: /var/log/barman/cron.log"

echo "$(date '+%Y-%m-%d %H:%M:%S'): Инициализация Barman успешно завершена"
sleep 2

# Проверка конфигурации
echo "Проверка конфигурации Barman:"
#barman check db >> /var/log/barman/check.log 2>&1
barman check db 2>&1 | tee -a /var/log/barman/check.log

# Команда, которая удержит контейнер активным (выполняется от barman)
exec sleep infinity
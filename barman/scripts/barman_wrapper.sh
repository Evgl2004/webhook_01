#!/bin/bash
# Универсальная обёртка. Использование:
#   barman_wrapper.sh <лог_файл> <команда> [аргументы...]

export TZ=Asia/Yekaterinburg

LOG_FILE="$1"    # Первый аргумент — путь к лог-файлу
shift            # Сдвигаем аргументы, чтобы $@ содержал только команду для выполнения

# Логируем запуск
# echo "=== [$(date '+%Y-%m-%d %H:%M:%S %Z')] Запуск: $@" >> "$LOG_FILE"

# Выполняем команду с добавлением временной метки к КАЖДОЙ строке вывода
"$@" 2>&1 | while IFS= read -r line; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] $line" >> "$LOG_FILE"
done

# Логируем код завершения
EXIT_CODE=${PIPESTATUS[0]}
echo "[$(date '+%Y-%m-%d %H:%M:%S %Z')] Завершено с кодом: $EXIT_CODE" >> "$LOG_FILE"
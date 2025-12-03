#!/bin/bash
set -e # Выходить при первой ошибке

echo "Начинаем инициализацию пользователей БД..."

# --- ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
if [ -z "$BARMAN_PASSWORD" ]; then
    echo "ОШИБКА: Переменная BARMAN_PASSWORD не установлена." >&2
    exit 1
fi

if [ -z "$STREAMING_BARMAN_PASSWORD" ]; then
    echo "ОШИБКА: Переменная STREAMING_BARMAN_PASSWORD не установлена." >&2
    exit 1
fi

echo "Переменные окружения получены."

# --- ВЫПОЛНЕНИЕ SQL ---
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    DO \$\$
    BEGIN
        -- Создание/проверка пользователя barman
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'barman') THEN
            EXECUTE format('CREATE USER barman WITH PASSWORD %L', '$BARMAN_PASSWORD');
            RAISE NOTICE 'Пользователь barman создан.';
        ELSE
            -- Обновление пароля для существующего пользователя (опционально, раскомментировать при необходимости)
            -- EXECUTE format('ALTER USER barman WITH PASSWORD %L', '$BARMAN_PASSWORD');
            RAISE NOTICE 'Пользователь barman уже существует.';
        END IF;

        -- Выдача прав пользователю barman (выполняется всегда, если пользователь существует)
        GRANT EXECUTE ON FUNCTION pg_backup_start(text, boolean) TO barman;
        GRANT EXECUTE ON FUNCTION pg_backup_stop(boolean) TO barman;
        GRANT pg_read_all_settings TO barman;
        GRANT pg_read_all_stats TO barman;
        RAISE NOTICE 'Права для пользователя barman выданы/обновлены.';

        -- Создание/проверка пользователя streaming_barman
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'streaming_barman') THEN
            EXECUTE format('CREATE USER streaming_barman WITH REPLICATION PASSWORD %L', '$STREAMING_BARMAN_PASSWORD');
            RAISE NOTICE 'Пользователь streaming_barman создан.';
        ELSE
            -- Обновление пароля для существующего пользователя (опционально)
            -- EXECUTE format('ALTER USER streaming_barman WITH PASSWORD %L', '$STREAMING_BARMAN_PASSWORD');
            RAISE NOTICE 'Пользователь streaming_barman уже существует.';
        END IF;
    END
    \$\$;
EOSQL

echo "Инициализация пользователей БД успешно завершена."
EOF
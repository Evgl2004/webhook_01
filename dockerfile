FROM python:3.13-slim

WORKDIR /app

# 1. Установка системных зависимостей
# RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# 2. Копирование списка используемых пакетов и установка зависимостей Python (отдельный слой для кэширования)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Копирование проекта
COPY . .

# 4. Создание пользователя для безопасности
# RUN useradd -m -r app && chown -R app:app /app
# USER app

# 5. Команда по умолчанию (будет переопределена в docker-compose)
# CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]

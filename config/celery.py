import os
from celery import Celery

# Установка переменной окружения для настроек проекта
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Создание экземпляра объекта Celery
app = Celery('config')

# Загрузка настроек из файла Django
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение и регистрация задач из файлов tasks.py в приложениях Django
app.autodiscover_tasks()

# Если при запуске воркера брокер недоступен, Celery будет периодически пытаться подключиться с увеличивающимися
# интервалами, пока соединение не будет установлено или не будет достигнут предел попыток.
# Это стандартное и рекомендуемое поведение.
app.conf.broker_connection_retry_on_startup = True

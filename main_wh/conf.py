from django.conf import settings


class AppSettings:
    """
    Настройки для приложения main_webhook.
    Значения по умолчанию определены здесь.
    """

    def __init__(self, prefix='WEBHOOK'):
        self.prefix = prefix

    def _get_setting(self, name, default):
        # Формируем имя настройки, например, 'WEBHOOK'_REDIS_QUEUE_URL
        # Если префикс не пустой, добавляем его и подчеркивание.
        # Если префикс пустой, используем только имя настройки.
        if self.prefix:
            full_name = f"{self.prefix}_{name}"
        else:
            full_name = name  # Без лишнего подчеркивания!
        # ЛЕНИВАЯ ЗАГРУЗКА: обращаемся к settings только здесь
        return getattr(settings, full_name, default)

    @property
    def REDIS_QUEUE_URL(self):
        return self._get_setting('REDIS_QUEUE_URL', 'redis://redis:6379/1')

    @property
    def REDIS_QUEUE_NAME(self):
        return self._get_setting('REDIS_QUEUE_NAME', 'webhook_queue')

# Создаём глобальный объект для импорта
app_settings = AppSettings('')

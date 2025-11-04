from django.db import models
from django.core.validators import MaxLengthValidator
from django.utils import timezone
from datetime import datetime

NULLABLE = {'null': True, 'blank': True}


class WebhookRequest(models.Model):
    # Класс с описанием Сущности Протокола входящих уведомлений.
    # Храним все поступающие уведомления.

    STATUS_NEW = 'new'
    STATUS_ERROR = 'error'
    STATUS_COMPLETE = 'complete'

    STATUS_REQUEST = (
        (STATUS_NEW, 'Новый'),
        (STATUS_ERROR, 'Ошибка'),
        (STATUS_COMPLETE, 'Завершено'),
    )

    # Основные реквизиты
    inserted_at = models.DateTimeField(auto_now_add=True, verbose_name='ДатаВремя добавления')
    request_method = models.CharField(max_length=10, default='POST', verbose_name='HTTP метод запроса')
    path = models.CharField(max_length=254, default='', verbose_name='Точка вызова')
    full_url = models.URLField (max_length=500, default='', verbose_name='Полная строка вызова')
    user_agent = models.CharField(max_length=254, default='', verbose_name='User Agent отправителя')
    ip_adr = models.GenericIPAddressField(protocol='IPv4', default='0.0.0.0', verbose_name='IP адрес отправителя')
    content_type = models.CharField(max_length=254, default='', verbose_name='Контент в заголовках')

    # Данные запроса
    parsed_query = models.JSONField(default=dict, verbose_name='Разобранные параметры запроса')
    data = models.TextField(validators=[MaxLengthValidator(5000)], default='', verbose_name='Тело запроса')

    # Статус обработки
    status = models.CharField(max_length=20,choices=STATUS_REQUEST, default=STATUS_NEW, verbose_name='Статус обработки')
    error_description = models.TextField(validators=[MaxLengthValidator(5000)], default='', verbose_name='Текст ошибки')
    processed_at = models.DateTimeField(default=timezone.make_aware(datetime(1970, 1, 1, 0, 0, 0)), verbose_name='ДатаВремя обработки')

    class Meta:
        verbose_name = 'Входящее уведомление'
        verbose_name_plural = 'Входящие уведомления'
        ordering = ['-inserted_at']
        indexes = [
            models.Index(fields=['status', 'inserted_at']),
        ]

    def __str__(self):
        return f"Уведомление {self.id} от {self.inserted_at.strftime('%H:%M %d.%m.%Y')}"

    def save(self, *args, **kwargs):
        # При изменении статуса на "завершено" или "ошибка" фиксируем время обработки
        if self.status in [self.STATUS_ERROR, self.STATUS_COMPLETE] and not self.processed_at:
            self.processed_at = timezone.now
        super().save(*args, **kwargs)
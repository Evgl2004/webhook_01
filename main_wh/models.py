from django.db import models
from django.core.validators import MaxLengthValidator, URLValidator
from django.utils import timezone
from datetime import datetime

NULLABLE = {'null': True, 'blank': True}


class CategoryWebhook(models.Model):
    """
    Класс с описанием Сущности Категории для Уведомлений (Протокола входящих уведомлений).
    """

    # Внешний идентификатор (тот самый уникальный код)
    id_ext = models.CharField(max_length=32, unique=True, verbose_name='Внешний идентификатор')

    # Название для админки
    name = models.CharField(max_length=100, verbose_name='Название категории')

    # Описание
    description = models.TextField(max_length=500, default='', verbose_name='Описание')

    # Активна ли категория
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    # Дата создания
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')

    class Meta:
        verbose_name = 'Категория Уведомления'
        verbose_name_plural = 'Категории Уведомлений'
        ordering = ['name']
        indexes = [
            models.Index(fields=['id_ext', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.id_ext})"

    @classmethod
    def get_active_by_external_id(cls, external_id):
        """
        Получить активную категорию по внешнему идентификатору
        """

        try:
            return cls.objects.get(id_ext=external_id, is_active=True)
        except cls.DoesNotExist:
            return None

    @classmethod
    def is_valid_external_id(cls, external_id):
        """
        Проверить валидность внешнего идентификатора
        """

        return cls.objects.filter(id_ext=external_id, is_active=True).exists()

    @classmethod
    def get_active_categories(cls):
        """
        Получить все активные категории
        """

        return cls.objects.filter(is_active=True)

    def deactivate(self):
        """
        Деактивировать категорию
        """

        self.is_active = False
        self.save()


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
    full_url = models.URLField(max_length=500, validators=[URLValidator()], default='',
                               verbose_name='Полная строка вызова')
    user_agent = models.CharField(max_length=254, default='', verbose_name='User Agent отправителя')
    ip_adr = models.GenericIPAddressField(protocol='IPv4', default='0.0.0.0', verbose_name='IP адрес отправителя')
    content_type = models.CharField(max_length=254, default='', verbose_name='Контент в заголовках')

    # Данные запроса
    parsed_body = models.JSONField(max_length=10000, validators=[MaxLengthValidator(10000)], default=dict,
                                   verbose_name='Преобразованные данные')
    data = models.TextField(max_length=10000, validators=[MaxLengthValidator(10000)], default='',
                            verbose_name='Сырые данные')

    # Статус обработки
    status = models.CharField(max_length=20, choices=STATUS_REQUEST, default=STATUS_NEW,
                              verbose_name='Статус обработки')
    error_description = models.TextField(max_length=5000, validators=[MaxLengthValidator(5000)], default='',
                                         verbose_name='Текст ошибки')
    processed_at = models.DateTimeField(default=timezone.make_aware(datetime(1970, 1, 1, 0, 0, 0)),
                                        verbose_name='ДатаВремя обработки')

    # Связь с категорией
    category = models.ForeignKey(CategoryWebhook, on_delete=models.PROTECT, related_name='webhook_requests',
                                 verbose_name='Категория')

    class Meta:
        verbose_name = 'Входящее уведомление'
        verbose_name_plural = 'Входящие уведомления'
        ordering = ['-inserted_at']
        indexes = [
            models.Index(fields=['status', 'inserted_at']),
            models.Index(fields=['processed_at']),
        ]

    def __str__(self):
        return f"Уведомление {self.pk} от {self.inserted_at.strftime('%H:%M %d.%m.%Y')}"

    def save(self, *args, **kwargs):
        # При изменении статуса на "завершено" или "ошибка" фиксируем время обработки
        if self.status in [self.STATUS_ERROR, self.STATUS_COMPLETE] and not self.processed_at:
            self.processed_at = timezone.now()
        super().save(*args, **kwargs)

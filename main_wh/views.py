from django.utils import timezone

from rest_framework import status, generics
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.response import Response

from main_wh.models import WebhookRequest, CategoryWebhook
from main_wh.serializers import WebhookRequestSerializer
from main_wh.permissions import WebhookPermission, HealthCheckPermission
from main_wh.utils import get_client_ip

# Импортируем Celery задачу
from main_wh.tasks import process_webhook_notification

import logging
logger = logging.getLogger(__name__)


class WebhookRequestCreateAPIView(generics.CreateAPIView):
    """Описание точки входа для создания записей"""

    parser_classes = [JSONParser, FormParser]
    # Отключаем аутентификацию для webhook
    authentication_classes = []
    # Ограничиваем только методом POST
    permission_classes = [WebhookPermission]
    serializer_class = WebhookRequestSerializer

    # Использует лимит 'webhook' из настроек throttling
    throttle_scope = 'webhook'

    def create(self, request, *args, **kwargs):
        """
        Переопределяем метод создания записей для реализации задуманной логики
        """

        id_ext = kwargs.get('id_ext')

        # Проверяем существование категории
        try:
            find_category = CategoryWebhook.get_active_by_external_id(id_ext)
            if not find_category:
                # Возвращаем 404 без деталей для безопасности
                return Response(
                    {"status": "error", "message": "Not found"},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as err:
            # Записываем в журнал ошибку
            logger.error(f"Ошибка при направлении Уведомления: {str(err)}")

            # Любая ошибка - возвращаем 404
            return Response(
                {"status": "error", "message": "Not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # ЯВНАЯ проверка Content-Type
        allowed_content_types = [
            'application/json',
            'application/x-www-form-urlencoded'
        ]

        # Извлекает основной MIME-тип из заголовка Content-Type,
        # игнорируя кодировку и другие параметры.
        content_type_request = request.content_type
        if content_type_request:
            # Разделяем строку по точке с запятой и берем первую часть,
            # а также приводим к нижнему регистру для единообразия
            content_type_request = content_type_request.split(';')[0].strip().lower()

        if content_type_request not in allowed_content_types:
            logger.warning(f"Заблокирован неподдерживаемый Content-Type: {request.content_type} "
                           f"from IP: {get_client_ip(request)}")
            return Response(
                {"status": "error", "message": "Unsupported Content-Type"},
                status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
            )

        try:
            # Проверка размера данных
            if len(request.body) > 10000:  # Лимит из модели
                logger.error(f"Превышен допустимый размер данных from IP: {get_client_ip(request)}")
                return Response({
                    "status": "error",
                    "message": "Превышен допустимый размер данных"
                }, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

            # Извлечение полученных данных
            try:
                raw_body = request.body.decode('utf-8')
            except (AttributeError, UnicodeDecodeError):
                # Для бинарных данных или других кодировок
                raw_body = request.body.decode('utf-8', errors='replace')

            # ОБРАБОТКА РАЗНЫХ ФОРМАТОВ ДАННЫХ
            parsed_data = {}

            if content_type_request == 'application/json':
                # Для JSON используем request.data
                parsed_data = request.data if request.data else {}

            # Создание записи в протоколе
            notification = WebhookRequest.objects.create(
                path=request.path,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_adr=get_client_ip(request),
                parsed_body=parsed_data,
                data=raw_body,
                status='new',
                request_method=request.method,
                full_url=request.build_absolute_uri(),
                content_type=request.content_type,
                category=find_category,
            )

            # Запуск обработки полученных данных через Celery
            process_webhook_notification.delay(notification.id)

            # Возвращаем успешный ответ
            return Response({
                "status": "success",
                "message": "Успех! Уведомление принято!"
            }, status=status.HTTP_200_OK)

        except Exception as err:
            # Записываем в журнал ошибку, не пытаемся создавать уведомление об ошибке
            logger.error(f"Критическая ошибка при сохранении webhook: {str(err)}")

            return Response(
                {"status": "error", "message": str(err)},
                status=status.HTTP_400_BAD_REQUEST
            )


class HealthCheckAPIView(generics.RetrieveAPIView):
    """
    Точка доступа для проверки отклика состояния системы (облеченный health-check).
    Возвращает простой статус с timestamp.
    """

    # Отключаем аутентификацию для health-check
    authentication_classes = []
    # Ограничиваем только методом GET
    permission_classes = [HealthCheckPermission]

    # Используем отдельный лимит для health-check
    throttle_scope = 'healthcheck'

    def get(self, request, *args, **kwargs):
        """
        Простой health-check - всегда возвращает healthy
        """
        return Response({
            "status": "healthy",
            "timestamp": timezone.now().isoformat()
        })

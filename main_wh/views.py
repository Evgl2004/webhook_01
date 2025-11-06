from django.utils import timezone

from rest_framework import status, generics
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from main_wh.models import WebhookRequest
from main_wh.serializers import WebhookRequestSerializer
from main_wh.permissions import WebhookPermission, HealthCheckPermission
from main_wh.utils import get_client_ip

# Импортируем Celery задачу
from main_wh.tasks import process_webhook_notification

import logging
logger = logging.getLogger(__name__)


class WebhookRequestCreateAPIView(generics.CreateAPIView):
    """Описание точки входа для создания записей"""

    parser_classes = [JSONParser]
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
        try:
            # Проверка размера данных
            if len(request.body) > 5000:  # Лимит из модели
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

            # Создание записи в протоколе
            notification = WebhookRequest.objects.create(
                path=request.path,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_adr=get_client_ip(request),
                parsed_body=request.data if request.data else {},
                data=raw_body,
                status='new',
                request_method=request.method,
                full_url=request.build_absolute_uri(),
                content_type=request.content_type,
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
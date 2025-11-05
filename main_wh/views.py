from rest_framework import status, generics
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from main_wh.models import WebhookRequest
from main_wh.serializers import WebhookRequestSerializer
from main_wh.permissions import WebhookPermission
from main_wh.utils import get_client_ip

# Импортируем Celery задачу
from main_wh.tasks import process_webhook_notification

import logging


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
            # Извлечение полученных данных
            # raw_body = request.body.decode('utf-8') if request.body else ''
            try:
                raw_body = request.body.decode('utf-8')
            except (AttributeError, UnicodeDecodeError):
                try:
                    raw_body = request.body.decode('cp1251')  # Альтернативная кодировка
                except (AttributeError, UnicodeDecodeError):
                    raw_body = ''

            # Создание записи в протоколе
            notification = WebhookRequest.objects.create(
                path=request.path,
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                ip_adr=get_client_ip(request),
                parsed_query=dict(request.query_params),
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
            logger = logging.getLogger(__name__)
            logger.error(f"Критическая ошибка при сохранении webhook: {str(err)}")

            return Response(
                {"status": "error", "message": str(err)},
                status=status.HTTP_400_BAD_REQUEST
            )

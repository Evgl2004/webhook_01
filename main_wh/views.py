from rest_framework import status, generics
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from main_wh.models import WebhookRequest
from main_wh.serializers import WebhookRequestSerializer


class WebhookRequestCreateAPIView(generics.CreateAPIView):
    """Описание точки входа для создания записей"""

    parser_classes = [JSONParser]
    authentication_classes = []  # Отключаем аутентификацию для webhook
    permission_classes = []      # Отключаем проверки прав
    serializer_class = WebhookRequestSerializer

    def get_client_ip(self, request):
        """Получение IP адреса клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

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
                ip_adr=self.get_client_ip(request),
                parsed_query=dict(request.query_params),
                data=raw_body,
                status='new',
                request_method=request.method,
                full_url=request.build_absolute_uri(),
                content_type=request.content_type,
            )

            # Возвращаем успешный ответ
            return Response({
                "status": "success",
                "message": "Успех! Уведомление принято!"
            }, status=status.HTTP_200_OK)

        except Exception as err:
            # Записываем в журнал ошибку, не пытаемся создавать уведомление об ошибке
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Критическая ошибка при сохранении webhook: {str(err)}")

            return Response(
                {"status": "error", "message": str(err)},
                status=status.HTTP_400_BAD_REQUEST
            )

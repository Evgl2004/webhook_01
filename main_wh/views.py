from django.utils import timezone

from rest_framework import status, generics, filters
from rest_framework.parsers import JSONParser, FormParser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework.permissions import IsAuthenticated

from main_wh.models import WebhookRequest, CategoryWebhook
from main_wh.serializers import (WebhookRequestSerializer, WebhookRequestDetailSerializer,
                                 WebhookRequestUpdateSerializer)
from main_wh.permissions import (WebhookPermission, HealthCheckPermission,
                                 InternalServicePermission, WebhookReadPermission, WebhookUpdatePermission)
from main_wh.authentication import InternalServiceJWT
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


class WebhookPagination(PageNumberPagination):
    """
    Модифицированная нумерация страниц с метаданными сервиса
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,  # Общее количество (не только на странице!)
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data,
            'service': 'webhook_service',
            'version': '1.0',
            'page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'page_size': self.get_page_size(self.request)
        })


class WebhookRequestListAPIView(generics.ListAPIView):
    """
    Список Уведомлений с фильтрацией.
    """

    authentication_classes = [InternalServiceJWT]
    permission_classes = [IsAuthenticated, InternalServicePermission]
    serializer_class = WebhookRequestDetailSerializer
    pagination_class = WebhookPagination

    # Список фильтрации:
    # DjangoFilterBackend - фильтрация по конкретным полям
    # filters.OrderingFilter - сортировка результатов
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]

    # Поля, по которым доступна фильтрация через DjangoFilterBackend
    filterset_fields = ['id', 'status', 'business_status', 'category__id_ext']

    # Поля, по которым доступна сортировка через OrderingFilter
    ordering_fields = ['inserted_at', 'processed_at', 'business_processed_at']

    # Сортировка по умолчанию (по убыванию даты вставки)
    ordering = ['-inserted_at']

    # Метод получения QuerySet (набора данных) для этого представления
    def get_queryset(self):
        # Начинаем с менеджера модели
        # select_related('category') - оптимизация запроса: загружает связанную категорию одним запросом
        queryset = WebhookRequest.objects.select_related('category')

        # Фильтрация по дате: получаем параметры из query string запроса
        date_from = self.request.query_params.get('date_from')  # Дата начала периода
        date_to = self.request.query_params.get('date_to')  # Дата окончания периода

        # Применяем фильтры в оптимальном порядке
        if date_from and date_to:
            # Используем __range для одного условия вместо двух
            queryset = queryset.filter(inserted_at__range=[date_from, date_to])
        elif date_from:
            queryset = queryset.filter(inserted_at__gte=date_from)
        elif date_to:
            queryset = queryset.filter(inserted_at__lte=date_to)

        return queryset


class WebhookRequestRetrieveAPIView(generics.RetrieveAPIView):
    """
    Получение детальной информации об Уведомлении.
    """

    authentication_classes = [InternalServiceJWT]
    permission_classes = [InternalServicePermission, WebhookReadPermission]
    serializer_class = WebhookRequestDetailSerializer

    # Базовый QuerySet для этого представления
    queryset = WebhookRequest.objects.all().select_related('category')

    # Поле, используемое для поиска объекта.
    lookup_field = 'id'


class WebhookRequestUpdateAPIView(generics.UpdateAPIView):
    """
    Обновление бизнес-статуса Уведомления.
    Только для внутренних сервисов.
    Разрешает обновлять только business_processed_at и business_status.
    """

    authentication_classes = [InternalServiceJWT]
    permission_classes = [IsAuthenticated, InternalServicePermission, WebhookUpdatePermission]
    serializer_class = WebhookRequestUpdateSerializer

    # Базовый QuerySet
    queryset = WebhookRequest.objects.all()

    # Поле для поиска объекта
    lookup_field = 'id'

    # Разрешенные HTTP-методы (только PATCH, т.к. обновляем частично)
    http_method_names = ['patch']

    def get_queryset(self):
        """
        Оптимизированный QuerySet загружает ТОЛЬКО необходимые поля.
        1. id - для поиска и логирования
        2. business_status - для сравнения старого и нового значения
        3. business_processed_at - для проверки NULL_DATE и установки времени
        4. status - проверка статуса из списка.
        """

        # Импортируем NULL_DATE, если она используется в сериализаторе
        # from .models import NULL_DATE  # если нужно

        # Загружаем только необходимые поля
        return WebhookRequest.objects.only(
            'id',  # Для поиска и логирования
            'business_status',  # Для сравнения старого/нового значения
            'business_processed_at',  # Для проверки в update() сериализатора
            'status',  # Для проверки validate_business_status сериализатора
        )

    def get_serializer_context(self):
        """
        Метод для добавления дополнительного контекста в сериализатор.
        Добавляем имя сервиса в контекст для логирования
        """

        # Получаем контекст от родительского класса
        context = super().get_serializer_context()

        # Добавляем имя сервиса из заголовка HTTP_X_SERVICE_NAME
        context['service_name'] = self.request.META.get('HTTP_X_SERVICE_NAME', 'unknown')
        return context

    def patch(self, request, *args, **kwargs):
        """
        Переопределение метода PATCH для добавления логирования.
        """

        # Вызываем родительский метод PATCH
        response = super().patch(request, *args, **kwargs)

        # Если обновление прошло успешно (статус 200), логируем это
        if response.status_code == 200:
            logger.info(
                f"Уведомление {kwargs['id']} "
                f"обновлен сервисом {request.META.get('HTTP_X_SERVICE_NAME', 'unknown')}"
            )

        return response


class WebhookQueueStatsAPIView(generics.RetrieveAPIView):
    """
    Статистика Redis очереди.
    Только для внутренних сервисов.
    """

    authentication_classes = [InternalServiceJWT]
    permission_classes = [InternalServicePermission]

    # Метод обработки GET-запроса
    def get(self, request, *args, **kwargs):
        # Импорт здесь, чтобы избежать циклических импортов
        from .redis_client import redis_queue

        # Получаем статистику очереди из Redis-клиента
        stats = redis_queue.get_queue_stats()

        # Возвращаем статистику в виде JSON-ответа
        return Response(stats)

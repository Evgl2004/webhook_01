from rest_framework import serializers
from django.utils import timezone

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from main_wh.models import WebhookRequest, CategoryWebhook, NULL_DATE

import logging

logger = logging.getLogger(__name__)

class WebhookRequestSerializer(serializers.ModelSerializer):
    # Сериализатор для объектов Уведомлений, который ничего не показывает.

    class Meta:
        model = WebhookRequest
        # Абсолютно никаких полей
        fields = []

    def to_representation(self, instance):
        return {
            "message": "Доступ ограничен. Обратитесь к администратору."
        }


class CategoryWebhooksSerializer(serializers.ModelSerializer):
    # Минималистичный сериализатор для Категории Уведомлений.
    # С внешней стороны Категории не должны быть видны.

    class Meta:
        model = CategoryWebhook
        # Абсолютно никаких полей для внешнего API
        fields = []

    def to_representation(self, instance):
        return {
            "message": "Доступ к информации о категориях ограничен."
        }


class WebhookRequestDetailSerializer(serializers.ModelSerializer):
    """
    Сериализатор для детального просмотра Уведомления.
    Используется при GET-запросах для отображения всех деталей объекта Уведомлений.
    """

    # Создаем вычисляемое поле, которое будет брать значение из связанного объекта Категории Уведомлений.
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_id_ext = serializers.CharField(source='category.id_ext', read_only=True)
    processing_time = serializers.SerializerMethodField()

    class Meta:
        model = WebhookRequest
        fields = [
            'id',
            'inserted_at',
            'category_id_ext',
            'category_name',
            'status',
            'parsed_body',
            'content_type',
            'ip_adr',
            'processed_at',
            'business_queued_at',
            'business_processed_at',
            'business_status',
            'processing_time',
            'error_description'
        ]
        read_only_fields = fields  # Все поля только для чтения

    def get_processing_time(self, obj):
        """
        Вычисляем разницу между временем обработки и временем создания.
        Время обработки в секундах.
        """

        if obj.processed_at and obj.inserted_at:
            return (obj.processed_at - obj.inserted_at).total_seconds()
        return None


class WebhookRequestUpdateSerializer(serializers.ModelSerializer):
    """
    Сериализатор только для обновления бизнес-статуса.
    Используется при PATCH/PUT-запросах для обновления статуса обработки.
    """

    class Meta:
        model = WebhookRequest
        fields = ['business_processed_at', 'business_status']

    def validate_business_status(self, value):
        """
        Проверка поля business_status при обновлении.
        Вызывается автоматически перед сохранением данных.

        Args:
            value: Значение статуса, переданное в запросе
        """

        valid_statuses = ['pending', 'processing', 'complete', 'failed']
        if value not in valid_statuses:
            raise serializers.ValidationError(f"Статус должен быть одним из: {', '.join(valid_statuses)}")
        return value

    def update(self, instance, validated_data):
        """
        Переопределенный метод обновления объекта.
        Добавляет дополнительную логику при обновлении статуса.

        Args:
            instance: Существующий экземпляр WebhookRequest для обновления
            validated_data: Проверенные и очищенные данные для обновления
        """

        old_status = instance.business_status
        new_status = validated_data.get('business_status', old_status)

        # Устанавливаем время обработки, если статус стал 'completed'
        if new_status == 'complete' and instance.business_processed_at == NULL_DATE:
            validated_data['business_processed_at'] = timezone.now()

        # Обновляем объект стандартным способом
        instance = super().update(instance, validated_data)

        logger.info(
            f"Бизнес-статус Уведомления {instance.id} изменен: "
            f"{old_status} -> {new_status} "
            f"сервисом {self.context.get('service_name', 'unknown')}"
        )

        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Модифицированный сериализатор для добавления дополнительных claims в JWT токен
    """

    @classmethod
    def get_token(cls, user):
        """
        Переопределяем метод получения токена для добавления кастомных claims
        """
        token = super().get_token(user)

        # Добавляем claim для идентификации типа сервиса
        if user.username == 'business_service':  # Или другая логика
            token['service_type'] = 'internal_service'
            token['iss'] = 'webhook_service'  # Кто выпустил токен
            token['aud'] = 'business_service'  # Для кого предназначен
        else:
            token['service_type'] = 'regular_user'
            token['iss'] = 'webhook_service'
            token['aud'] = 'webhook_frontend'

        # Дополнительные claims
        token['user_id'] = user.id
        token['username'] = user.username

        return token

    def validate(self, attrs):
        """
        Переопределяем метод validate для корректного возврата токенов
        """
        try:
            # Вызываем родительский метод
            data = super().validate(attrs)

            # Получаем токен
            refresh = self.get_token(self.user)

            # Добавляем кастомные данные в ответ
            data.update({
                'user_id': self.user.id,
                'username': self.user.username,
                'service_type': refresh['service_type'] if 'service_type' in refresh else 'regular_user',
            })

            return data

        except Exception as err:
            logger.error(f"Ошибка в CustomTokenObtainPairSerializer: {str(err)}")
            raise serializers.ValidationError({
                "detail": "Ошибка аутентификации"
            })
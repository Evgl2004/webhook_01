from rest_framework import serializers

from main_wh.models import WebhookRequest, CategoryWebhook


class WebhookRequestSerializer(serializers.ModelSerializer):
    # Сериализатор, который ничего не показывает

    class Meta:
        model = WebhookRequest
        # Абсолютно никаких полей
        fields = []

    def to_representation(self, instance):
        return {
            "message": "Доступ ограничен. Обратитесь к администратору."
        }


class CategoryWebhooksSerializer(serializers.ModelSerializer):
    # Минималистичный сериализатор для Категории Уведомлений
    # С внешней стороны Категории не должны быть видны

    class Meta:
        model = CategoryWebhook
        # Абсолютно никаких полей для внешнего API
        fields = []

    def to_representation(self, instance):
        return {
            "message": "Доступ к информации о категориях ограничен."
        }

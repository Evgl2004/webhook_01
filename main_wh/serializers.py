from rest_framework import serializers

from main_wh.models import WebhookRequest


class WebhookRequestSerializer(serializers.ModelSerializer):
    # Сериализатор, который ничего не показывает

    class Meta:
        model = WebhookRequest
        # Абсолютно никаких полей
        fields = []

    def to_representation(self, instance):
        return {
            "id": instance.id,
            "message": "Доступ ограничен. Обратитесь к администратору."
        }
from django.urls import path
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.routers import DefaultRouter

from main_wh.apps import MainWhConfig
from main_wh.views import WebhookRequestCreateAPIView, HealthCheckAPIView

app_name = MainWhConfig.name

router = DefaultRouter()


def health_check(request):
    return JsonResponse({"status": "healthy", "timestamp": timezone.now().isoformat()})


urlpatterns = [
    path('webhooks/<str:id_ext>', WebhookRequestCreateAPIView.as_view(), name='webhook_create'),
    path('health', HealthCheckAPIView.as_view(), name='health_check'),
] + router.urls

from django.urls import path
from django.http import JsonResponse
from django.utils import timezone
from rest_framework.routers import DefaultRouter

from main_wh.apps import MainWhConfig
from main_wh.views import (WebhookRequestCreateAPIView, HealthCheckAPIView, WebhookRequestListAPIView,
                           WebhookRequestRetrieveAPIView, WebhookRequestUpdateAPIView, WebhookQueueStatsAPIView,)

from rest_framework_simplejwt.views import (TokenObtainPairView, TokenRefreshView, TokenVerifyView)
from main_wh.serializers import CustomTokenObtainPairSerializer


app_name = MainWhConfig.name

router = DefaultRouter()


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


def health_check(request):
    return JsonResponse({"status": "healthy", "timestamp": timezone.now().isoformat()})


urlpatterns = [
    path('webhooks/<str:id_ext>', WebhookRequestCreateAPIView.as_view(), name='webhook_create'),
    path('health', HealthCheckAPIView.as_view(), name='health_check'),

    # Внутренние API (только для сервисов)
    path('api/internal/webhooks/', WebhookRequestListAPIView.as_view(), name='webhook_list'),
    path('api/internal/webhooks/<int:id>/', WebhookRequestRetrieveAPIView.as_view(), name='webhook_detail'),
    path('api/internal/webhooks/<int:id>/update/', WebhookRequestUpdateAPIView.as_view(), name='webhook_update'),
    path('api/internal/queue/stats/', WebhookQueueStatsAPIView.as_view(), name='queue_stats'),

    # Получение, продление токенов авторизации
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),

] + router.urls

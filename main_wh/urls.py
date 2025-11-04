from django.urls import path
from rest_framework.routers import DefaultRouter

from main_wh.apps import MainWhConfig
from main_wh.views import WebhookRequestCreateAPIView

app_name = MainWhConfig.name

router = DefaultRouter()


urlpatterns = [
    path('webhooks/v1/phajA9JMvruP8bhJJQOYzs8vwKlFiX6f/', WebhookRequestCreateAPIView.as_view(), name='webhook_create'),
    # path('webhookrequest/create/', WebhookRequestCreateAPIView.as_view(), name='webhook_create'),
] + router.urls
from django.contrib import admin
from main_wh.models import WebhookRequest


@admin.register(WebhookRequest)
class WebhookRequestAdmin(admin.ModelAdmin):
    list_display = ('pk', 'inserted_at', 'path')
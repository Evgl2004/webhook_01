from django.contrib import admin
from main_wh.models import WebhookRequest


@admin.register(WebhookRequest)
class WebhookRequestAdmin(admin.ModelAdmin):
    list_display = ('pk', 'inserted_at', 'path', 'status', 'processed_at')
    list_filter = ('status', 'inserted_at')
    search_fields = ('path', 'ip_adr')
    readonly_fields = ('inserted_at', 'processed_at')

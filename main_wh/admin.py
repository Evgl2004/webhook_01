from django.contrib import admin
from main_wh.models import WebhookRequest, CategoryWebhook


@admin.register(WebhookRequest)
class WebhookRequestAdmin(admin.ModelAdmin):
    list_display = ('pk', 'inserted_at', 'category', 'status', 'processed_at')
    list_filter = ('status', 'inserted_at', 'category')
    search_fields = ('path', 'ip_adr', 'category__name', 'category__id_ext')
    readonly_fields = ('inserted_at', 'processed_at')
    list_select_related = ('category',)

    # Оставляем только кнопку просмотра
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['category'].widget.can_add_related = False
        form.base_fields['category'].widget.can_change_related = False
        form.base_fields['category'].widget.can_delete_related = False
        # can_view_related остается True по умолчанию
        return form

    # Добавляем фильтр по категории в правую боковую панель
    def get_list_filter(self, request):
        return ('status', 'inserted_at', 'category')

    # Добавляем поиск по external_id категории
    def get_search_fields(self, request):
        return ('path', 'ip_adr', 'category__name', 'category__id_ext')


@admin.register(CategoryWebhook)
class CategoryWebhookAdmin(admin.ModelAdmin):
    list_display = ('id_ext', 'name', 'is_active', 'created_at', 'webhook_count')
    list_filter = ('is_active', 'created_at')
    search_fields = ('id_ext', 'name', 'description')
    readonly_fields = ('created_at', 'webhook_count_display')
    actions = ['activate_categories', 'deactivate_categories']

    # Поля для формы редактирования
    fieldsets = (
        ('Основная информация', {
            'fields': ('id_ext', 'name', 'is_active')
        }),
        ('Описание', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        ('Статистика', {
            'fields': ('created_at', 'webhook_count_display'),
            'classes': ('collapse',)
        })
    )

    def webhook_count(self, obj):
        """Количество уведомлений в этой категории"""
        return obj.webhook_requests.count()

    webhook_count.short_description = 'Кол-во в уведомлениях'

    def webhook_count_display(self, obj):
        """Только для отображения в форме редактирования"""
        return obj.webhook_requests.count()

    webhook_count_display.short_description = 'Всего в уведомлениях'

    def activate_categories(self, request, queryset):
        """Активировать выбранные категории"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'Активировано {updated} категорий.')

    activate_categories.short_description = 'Активировать выбранные категории'

    def deactivate_categories(self, request, queryset):
        """Деактивировать выбранные категории"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'Деактивировано {updated} категорий.')

    deactivate_categories.short_description = 'Деактивировать выбранные категории'

    # Запрещаем удаление категорий, у которых есть уведомлений
    def has_delete_permission(self, request, obj=None):
        if obj and obj.webhook_requests.exists():
            return False
        return super().has_delete_permission(request, obj)

    # Сообщение при попытке удалить категорию у которой есть уведомления
    def delete_queryset(self, request, queryset):
        # Проверяем, есть ли категории с уведомлениями
        categories_with_webhooks = queryset.filter(webhook_requests__isnull=False).distinct()
        if categories_with_webhooks.exists():
            self.message_user(
                request,
                f'Невозможно удалить категории с уведомление: {", ".join(str(c) for c in categories_with_webhooks)}',
                level='ERROR'
            )
            # Удаляем только категории без уведомлений
            queryset = queryset.filter(webhook_requests__isnull=True)

        count = queryset.count()
        queryset.delete()
        if count > 0:
            self.message_user(request, f'Удалено {count} категорий.')

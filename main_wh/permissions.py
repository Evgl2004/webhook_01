from rest_framework import permissions


class WebhookPermission(permissions.BasePermission):
    """Разрешение только для POST запросов к webhook"""
    def has_permission(self, request, view):
        return request.method == 'POST'


class HealthCheckPermission(permissions.BasePermission):
    """Разрешение только для GET запросов к HealthCheck"""
    def has_permission(self, request, view):
        return request.method == 'GET'


class InternalServicePermission(permissions.BasePermission):
    """
    Разрешение только для внутренних сервисов.
    """

    def has_permission(self, request, view):
        # Проверяем, что пользователь аутентифицирован нашим методом
        if request.user and request.user.username == 'business_service':
            return True
        return False


class WebhookUpdatePermission(permissions.BasePermission):
    """
    Разрешение только на обновление business_processed_at и business_status.
    """

    def has_permission(self, request, view):
        return request.method == 'PATCH'

    def has_object_permission(self, request, view, obj):
        if request.method == 'PATCH':
            # Разрешаем обновлять только business_* поля
            allowed_fields = {'business_processed_at', 'business_status'}
            actual_fields = set(request.data.keys())

            # Проверяем, что запрос пытается изменить только разрешенные поля
            return actual_fields.issubset(allowed_fields)

        return False


class WebhookReadPermission(permissions.BasePermission):
    """
    Только для получения данных Уведомлений.
    """

    def has_permission(self, request, view):
        return request.method == 'GET'

from rest_framework import permissions


class WebhookPermission(permissions.BasePermission):
    """Разрешение только для POST запросов к webhook"""
    def has_permission(self, request, view):
        return request.method == 'POST'


class HealthCheckPermission(permissions.BasePermission):
    """Разрешение только для GET запросов к HealthCheck"""
    def has_permission(self, request, view):
        return request.method == 'GET'

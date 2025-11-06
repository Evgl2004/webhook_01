from celery import shared_task
from main_wh.models import WebhookRequest
from main_wh.utils import WebhookProcessor

from django.utils import timezone
from datetime import timedelta

import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def process_webhook_notification(self, notification_id):
    """
    Задача Celery для обработки одного уведомления
    """
    try:
        try:
            notification = WebhookRequest.objects.get(id=notification_id)
            WebhookProcessor.process_single_notification(notification)

            logger.info(f"Уведомление {notification_id} обработано через Celery")
            return f"Уведомление {notification_id} обработано успешно!"

        except WebhookRequest.DoesNotExist:
            logger.error(f"Уведомление {notification_id} не найдено")
            return f"Уведомление {notification_id} не найдено"

        except Exception as err:
            # Повторяем задачу через 60 секунд при ошибке
            logger.error(f"Ошибка обработки уведомления {notification_id}: {str(err)}")
            raise self.retry(countdown=60, exc=err)

    except ConnectionError as err:
        logger.error(f"Ошибка подключения к Redis: {err}")
        raise self.retry(countdown=60, exc=err)

@shared_task
def process_pending_notifications():
    """
    Обработка всех ожидающих уведомлений со статусом 'новый'
    """
    WebhookProcessor.process_pending_notifications()
    return "Успешно завершена обработка ожидающих уведомлений!"


@shared_task
def retry_failed_notifications():
    """
    Задача для повторной обработки уведомлений со статусом 'ошибка'
    """
    failed_notifications = WebhookRequest.objects.filter(status='error')

    for notification in failed_notifications:
        notification.status = 'new'
        notification.error_description = ''
        notification.processed_at = None
        notification.save()

        # Запускаем обработку в фоне
        process_webhook_notification.delay(notification.id)

    return f"Повторная попытка {failed_notifications.count()} обработки уведомления с ошибкой"


@shared_task
def cleanup_old_notifications(days_old=30):
    """
    Очистка старых уведомлений для экономии места
    """

    cutoff_date = timezone.now() - timedelta(days=days_old)
    deleted_count = WebhookRequest.objects.filter(
        inserted_at__lt=cutoff_date
    ).delete()[0]

    logger.info(f"Очищено {deleted_count} уведомлений старше {days_old} дней")
    return f"Очищено {deleted_count} уведомлений старше {days_old} дней"

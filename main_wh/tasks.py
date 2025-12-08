from celery import shared_task
from main_wh.models import WebhookRequest
from main_wh.utils import WebhookProcessor

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from datetime import timedelta

from main_wh.redis_client import redis_queue

import logging

logger = logging.getLogger(__name__)


# Декоратор для создания Celery задачи с параметрами:
# - bind=True: позволяет получить доступ к самому объекту задачи (self)
# - max_retries=3: максимальное количество повторных попыток при ошибке
@shared_task(bind=True, max_retries=3)
def process_webhook_notification(self, notification_id):
    """
    Задача Celery для обработки одного уведомления
    """
    try:
        try:
            # Получаем объект уведомления из базы данных по ID
            notification = WebhookRequest.objects.get(id=notification_id)

            # Вызываем статический метод обработчика для парсинга и обработки уведомления
            # Этот метод изменяет статус notification и заполняет parsed_body
            WebhookProcessor.process_single_notification(notification)

            # Проверяем статус уведомления после обработки
            # ТОЛЬКО если парсинг успешен, отправляем в очередь бизнес-сервиса
            if notification.status == 'complete':
                # Подготавливаем данные для бизнес-сервиса
                webhook_data = {
                    'id': notification.id,
                    'category': notification.category.id_ext if notification.category else None,
                    'parsed_body': notification.parsed_body,
                    'raw_data': notification.data[:1000],  # Первые 1000 символов
                    'created_at': notification.inserted_at.isoformat(),
                    'content_type': notification.content_type,
                    'source_ip': notification.ip_adr
                }

                # Отправляем подготовленные данные в Redis очередь бизнес-сервиса
                # send_to_business_queue возвращает True при успешной отправке
                if redis_queue.send_to_business_queue(webhook_data):
                    # Если отправка успешна, сохраняем метку времени отправки в очередь
                    notification.business_queued_at = timezone.now()
                    # Частичное обновление только одного поля в базе данных
                    notification.save(update_fields=['business_queued_at'])

                    logger.info(f"Уведомление {notification_id} отправлено в бизнес-очередь")
                else:
                    logger.warning(f"Уведомление {notification_id} не отправлено в бизнес-очередь")

            logger.info(f"Уведомление {notification_id} обработано через Celery")
            return f"Уведомление {notification_id} обработано успешно!"

        # Обрабатываем случай, когда уведомление не найдено в базе данных
        except ObjectDoesNotExist:
            logger.error(f"Уведомление {notification_id} не найдено")
            return f"Уведомление {notification_id} не найдено"

        # Обрабатываем все остальные исключения во время обработки
        except Exception as err:
            # Повторяем задачу через 60 секунд при ошибке
            logger.error(f"Ошибка обработки уведомления {notification_id}: {str(err)}")
            # Инициируем повторное выполнение задачи через 60 секунд
            # exc=err передает оригинальное исключение для логирования в Celery
            raise self.retry(countdown=60, exc=err)

    # Обрабатываем специфическую ошибку подключения к Redis
    except ConnectionError as err:
        logger.error(f"Ошибка подключения к Redis: {err}")
        # Обрабатываем специфическую ошибку подключения к Redis
        # exc=err передает оригинальное исключение для логирования в Celery
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


# Декоратор для создания обычной задачи Celery (без bind=True, так как не нужен доступ к self)
@shared_task
def check_queue_health():
    """
    Проверка здоровья Redis очереди (проверка очереди).
    """

    # Получаем статистику очереди из Redis клиента
    stats = redis_queue.get_queue_stats()
    logger.info(f"Статистика очереди: {stats}")

    # Возвращаем статистику как результат задачи
    return stats

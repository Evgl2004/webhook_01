import json
import logging
from django.utils import timezone
from main_wh.models import WebhookRequest
from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """
    Получение IP адреса клиента.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class WebhookProcessor:
    """
    Класс для безопасного парсинга и валидации входящих уведомлений
    """

    @classmethod
    def safe_parse_form_data(cls, notification, max_size=10000, max_params=50):
        """
        Безопасный парсинг form-data с защитой от переполнения и атак
        """
        try:
            # 1. ПРОВЕРКА РАЗМЕРА
            body = notification.data
            if len(body) > max_size:
                notification.status = 'error'
                notification.error_description = f"Превышен максимальный размер данных: {len(body)} > {max_size}"
                notification.processed_at = timezone.now()
                notification.save()
                logger.warning(f"Webhook {notification.id}: превышен размер данных")
                return

            # 2. ПАРСИНГ С ПРОВЕРКОЙ СТРУКТУРЫ
            parsed_qs = parse_qs(body, strict_parsing=True)

            # 3. ПРОВЕРКА КОЛИЧЕСТВА ПАРАМЕТРОВ
            if len(parsed_qs) > max_params:
                notification.status = 'error'
                notification.error_description = f"Превышено максимальное количество параметров: {len(parsed_qs)} > {max_params}"
                notification.processed_at = timezone.now()
                notification.save()
                logger.warning(f"Webhook {notification.id}: слишком много параметров")
                return

            # 4. БЕЗОПАСНОЕ ПРЕОБРАЗОВАНИЕ
            result = {}
            for key, values in parsed_qs.items():
                # Ограничение длины ключа
                if len(key) > 100:
                    continue

                if values:
                    value = values[0]

                    # БЕЗОПАСНЫЙ ПАРСИНГ ВЛОЖЕННОГО JSON
                    if key in ['payload', 'data', 'json']:
                        if len(value) <= 5000:  # Лимит для JSON
                            if value.strip().startswith('{') or value.strip().startswith('['):
                                try:
                                    parsed_json = json.loads(value)
                                    if cls.is_safe_json_structure(parsed_json, max_depth=5):
                                        result[key] = parsed_json
                                    else:
                                        result[key] = value[:1000]  # Обрезаем слишком сложные структуры
                                except json.JSONDecodeError:
                                    result[key] = value[:1000]
                    else:
                        # Для обычных полей
                        if len(value) <= 1000:
                            result[key] = value

            # 5. СОХРАНЕНИЕ РЕЗУЛЬТАТА
            notification.parsed_body = result
            notification.status = 'complete'
            notification.processed_at = timezone.now()
            notification.save()
            logger.info(f"Webhook {notification.id}: успешно обработан (form-data)")

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Ошибка парсинга form-data: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.error(f"Webhook {notification.id}: ошибка парсинга form-data: {str(err)}")

    @classmethod
    def safe_parse_json_data(cls, notification, max_size=10000):
        """
        Безопасный парсинг JSON данных
        """
        try:
            # 1. ПРОВЕРКА РАЗМЕРА
            body = notification.data
            if len(body) > max_size:
                notification.status = 'error'
                notification.error_description = f"Превышен максимальный размер JSON: {len(body)} > {max_size}"
                notification.processed_at = timezone.now()
                notification.save()
                logger.warning(f"Webhook {notification.id}: превышен размер JSON")
                return

            # 2. ПАРСИНГ JSON
            if body.strip():
                parsed_data = json.loads(body)

                # 3. ПРОВЕРКА СТРУКТУРЫ JSON
                if not cls.is_safe_json_structure(parsed_data, max_depth=10):
                    notification.status = 'error'
                    notification.error_description = "Слишком сложная структура JSON"
                    notification.processed_at = timezone.now()
                    notification.save()
                    logger.warning(f"Webhook {notification.id}: слишком сложная JSON структура")
                    return

                # 4. СОХРАНЕНИЕ РЕЗУЛЬТАТА
                notification.parsed_body = parsed_data
                notification.status = 'complete'
                notification.processed_at = timezone.now()
                notification.save()
                logger.info(f"Webhook {notification.id}: успешно обработан (JSON)")
            else:
                # Пустой JSON
                notification.parsed_body = {}
                notification.status = 'complete'
                notification.processed_at = timezone.now()
                notification.save()

        except json.JSONDecodeError as err:
            notification.status = 'error'
            notification.error_description = f"Невалидный JSON: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.warning(f"Webhook {notification.id}: невалидный JSON: {str(err)}")
        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Ошибка парсинга JSON: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.error(f"Webhook {notification.id}: ошибка парсинга JSON: {str(err)}")

    @classmethod
    def is_safe_json_structure(cls, data, max_depth=5, current_depth=0):
        """
        Проверка, что JSON не слишком сложный/глубокий для безопасности
        """
        if current_depth > max_depth:
            return False

        if isinstance(data, dict):
            # Ограничение количества ключей в объекте
            if len(data) > 100:
                return False

            for value in data.values():
                if not cls.is_safe_json_structure(value, max_depth, current_depth + 1):
                    return False

        elif isinstance(data, list):
            # Ограничение длины массива
            if len(data) > 1000:
                return False

            for item in data:
                if not cls.is_safe_json_structure(item, max_depth, current_depth + 1):
                    return False

        return True

    @classmethod
    def validate_content_type(cls, content_type):
        """
        Валидация Content-Type
        """
        allowed_content_types = [
            'application/json',
            'application/x-www-form-urlencoded'
        ]

        if content_type:
            content_type = content_type.split(';')[0].strip().lower()
            return content_type in allowed_content_types
        return False

    @classmethod
    def validate_data_size(cls, data, max_size=10000):
        """
        Валидация размера данных
        """
        return len(data) <= max_size

    @classmethod
    def process_single_notification(cls, notification):
        """
        Основной метод обработки уведомления - ТОЛЬКО ПАРСИНГ И ВАЛИДАЦИЯ
        """
        logger.info(f"Начало обработки уведомления {notification.id}")

        try:
            # 1. ВАЛИДАЦИЯ CONTENT-TYPE
            if not cls.validate_content_type(notification.content_type):
                notification.status = 'error'
                notification.error_description = f"Неподдерживаемый Content-Type: {notification.content_type}"
                notification.processed_at = timezone.now()
                notification.save()
                logger.warning(f"Webhook {notification.id}: неподдерживаемый Content-Type")
                return

            # 2. ВАЛИДАЦИЯ РАЗМЕРА ДАННЫХ
            if not cls.validate_data_size(notification.data):
                notification.status = 'error'
                notification.error_description = f"Превышен максимальный размер данных"
                notification.processed_at = timezone.now()
                notification.save()
                logger.warning(f"Webhook {notification.id}: превышен размер данных")
                return

            # 3. ПАРСИНГ В ЗАВИСИМОСТИ ОТ CONTENT-TYPE
            content_type = notification.content_type.split(';')[0].strip().lower()

            if content_type == 'application/x-www-form-urlencoded':
                cls.safe_parse_form_data(notification)
            elif content_type == 'application/json':
                cls.safe_parse_json_data(notification)
            else:
                # Для неизвестных типов просто сохраняем сырые данные
                # notification.parsed_body = {"raw_data": notification.data[:1000]}  # Обрезаем для безопасности
                # notification.status = 'complete'
                # logger.info(f"Webhook {notification.id}: обработан как сырые данные")
                notification.parsed_body = {}
                notification.status = 'error'
                notification.error_description = f"Неизвестный тип content_type!"
                notification.processed_at = timezone.now()
                notification.save()
                logger.error(f"Неизвестный тип content_type! при обработки уведомления {notification.id}")

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Критическая ошибка обработки: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.error(f"Критическая ошибка обработки уведомления {notification.id}: {str(err)}")

    @classmethod
    def process_pending_notifications(cls):
        """
        Обработка всех уведомлений со статусом 'новый'
        """
        pending_notifications = WebhookRequest.objects.filter(status='new')
        total_count = pending_notifications.count()

        if total_count == 0:
            logger.info("Нет ожидающих уведомлений для обработки")
            return

        logger.info(f"Начало обработки {total_count} ожидающих уведомлений")

        # Ограничение на batch processing
        batch_size = 100
        processed_count = 0
        error_count = 0

        for notification in pending_notifications[:batch_size]:
            try:
                cls.process_single_notification(notification)
                processed_count += 1
            except Exception as err:
                error_count += 1
                logger.error(f"Критическая ошибка обработки уведомления {notification.id}: {str(err)}")

        logger.info(
            f"Обработка завершена. "
            f"Успешно: {processed_count}, "
            f"Ошибок: {error_count}, "
            f"Всего: {total_count}"
        )

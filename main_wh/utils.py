import json
import logging
from django.utils import timezone
from main_wh.models import WebhookRequest
from config.settings import REQUIRED_PASSWORD

from urllib.parse import parse_qs

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """
    Получение IP адреса клиента.
    Используется при обработке входящего запроса.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


class WebhookProcessor:
    """Базовый класс для обработки webhook - ВСЯ логика в фоне"""

    @classmethod
    def safe_parse_form_data(cls, notification, max_size=5000, max_params=100):
        """
        Безопасный парсинг form-data - использует данные из views.py как основу
        """

        try:
            # 1. ПРОВЕРКА РАЗМЕРА - ЗАЩИТА ОТ ПЕРЕПОЛНЕНИЯ
            body = notification.data
            if len(body) > max_size:
                notification.status = 'error'
                notification.error_description = f"Ошибка обработки: data_too_large"
                notification.processed_at = timezone.now()
                notification.save()
                logger.warning(f"Ошибка обработки: data_too_large")
                return

            # 2. ПАРСИНГ С ПРОВЕРКОЙ СТРУКТУРЫ
            parsed_qs = parse_qs(body, strict_parsing=True)

            # 3. ПРОВЕРКА КОЛИЧЕСТВА ПАРАМЕТРОВ - ЗАЩИТА ОТ АТАК
            if len(parsed_qs) > max_params:
                notification.status = 'error'
                notification.error_description = f"Ошибка обработки: too_many_parameters"
                notification.processed_at = timezone.now()
                notification.save()
                logger.warning(f"Ошибка обработки: too_many_parameters")
                return

            # 4. БЕЗОПАСНОЕ ПРЕОБРАЗОВАНИЕ С ОГРАНИЧЕНИЯМИ
            result = {}

            for key, values in parsed_qs.items():
                # Ограничение длины ключа
                if len(key) > 100:
                    continue

                if values:  # Ограничение длины значения
                    value = values[0]

                    # 5. БЕЗОПАСНЫЙ ПАРСИНГ
                    if key in ['payload', 'data', 'json']:
                        # Увеличиваем лимит для JSON
                        if len(value) <= 10000:
                            # БЕЗОПАСНЫЙ JSON ПАРСИНГ
                            if value.strip().startswith('{'):
                                try:
                                    parsed_json = json.loads(value)
                                    if cls.is_safe_json_structure(parsed_json, max_depth=5):
                                        result[key] = parsed_json
                                    else:
                                        result[key] = value
                                except json.JSONDecodeError:
                                    result[key] = value
                    else:
                        # Для обычных полей оставляем старый лимит
                        if len(value) <= 1000:
                            result[key] = value

            # 6. СОХРАНЕНИЕ РЕЗУЛЬТАТА
            notification.parsed_body = result
            notification.status = 'complete'
            notification.processed_at = timezone.now()
            notification.save()

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Не удалось выполнить преобразование представления данных: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.warning(f"Не удалось выполнить преобразование представления данных: {str(err)}")

    @classmethod
    def is_safe_json_structure(cls, data, max_depth=5, current_depth=0):
        """
        Проверка, что JSON не слишком сложный/глубокий
        """

        if current_depth > max_depth:
            return False

        if isinstance(data, dict):
            for value in data.values():
                if not cls.is_safe_json_structure(value, max_depth, current_depth + 1):
                    return False
        elif isinstance(data, list):
            for item in data:
                if not cls.is_safe_json_structure(item, max_depth, current_depth + 1):
                    return False

        return True

    @classmethod
    def parse_notification_data(cls, notification):
        """
        Разбираем структуру данных из уведомлений.
        Возвращаем разобранные данные или None, если не JSON.
        """
        try:
            if notification.data:
                return json.loads(notification.data)
            return None
        except (json.JSONDecodeError, TypeError) as err:
            logger.warning(f"Уведомление {notification.id} - невалидный JSON: {str(err)}")
            return None

    @classmethod
    def validate_password(cls, parsed_data):
        """
        Проверка пароля
        """
        if not parsed_data or not isinstance(parsed_data, dict):
            return False

        # Проверяем различные возможные названия поля с паролем
        password_fields = ['subscriptionPassword', 'password', 'secret', 'token']

        for field in password_fields:
            password = parsed_data.get(field)
            if password and password == REQUIRED_PASSWORD:
                return True

        return False

    @classmethod
    def extract_business_data(cls, parsed_data):
        """
        Извлекаем данные после проверки пароля
        """
        if not parsed_data or not isinstance(parsed_data, dict):
            return {}

        business_data = {}

        # Извлекаем guest_id из различных возможных полей
        guest_id_fields = ['customerId', 'guest_id', 'guestId', 'customer_id']
        for field in guest_id_fields:
            if field in parsed_data:
                business_data['guest_id'] = parsed_data[field]
                break

        # Извлекаем баланс
        balance_fields = ['balance', 'total_balance', 'totalBalance']
        for field in balance_fields:
            if field in parsed_data:
                try:
                    business_data['balance'] = float(parsed_data[field])
                    break
                except (ValueError, TypeError):
                    continue

        # Извлекаем venue_id
        venue_fields = ['organizationId', 'venue_id', 'venueId', 'organization_id']
        for field in venue_fields:
            if field in parsed_data:
                business_data['venue_id'] = parsed_data[field]
                break

        # Извлекаем имя гостя
        name_fields = ['guest_name', 'guestName', 'name']
        for field in name_fields:
            if field in parsed_data:
                business_data['guest_name'] = parsed_data[field]
                break

        # Если есть текст - пытаемся извлечь данные из текста
        if 'text' in parsed_data:
            text = parsed_data['text']
            # Извлечение баланса из текста
            if 'Итоговый Баланс (Guest.TotalBalance):' in text:
                try:
                    balance_part = text.split('Итоговый Баланс (Guest.TotalBalance):')[-1].split('\n')[0].strip()
                    balance_part = balance_part.replace(',', '').replace(' ', '')
                    business_data['balance'] = float(balance_part)
                except (ValueError, IndexError):
                    pass

            # Извлечение имени из текста
            if 'Имя (Guest.Name):' in text:
                try:
                    name_part = text.split('Имя (Guest.Name):')[-1].split('\n')[0].strip()
                    business_data['guest_name'] = name_part
                except IndexError:
                    pass

        return business_data

    @classmethod
    def process_single_notification(cls, notification):
        """
        Обработка одного уведомления - ВСЯ логика здесь
        """
        logger.info(f"Начало обработки уведомления {notification.id}")

        try:
            # 1. Разбираем полученную структуру данных
            # ВСЕГДА обрабатываем form-data в фоне
            if 'application/x-www-form-urlencoded' in notification.content_type:
                # Формат form-urlencoded - безопасный парсинг
                cls.safe_parse_form_data(notification)
            #parsed_data = cls.parse_notification_data(notification)

            # 2. Проверяем пароль
            #if not cls.validate_password(parsed_data):
            #    notification.status = 'error'
            #    notification.error_description = 'Неверный или отсутствующий пароль'
            #    notification.processed_at = timezone.now()
            #    notification.save()
            #    logger.warning(f"Уведомление {notification.id} - неверный пароль")
            #    return

            # 3. Извлекаем бизнес-данные (только после проверки пароля)
            #business_data = cls.extract_business_data(parsed_data)

            # 4. Определяем тип обработки по пути
            #if '/balance/' in notification.path:
            #    cls.process_balance_notification(notification, business_data, parsed_data)
            #elif '/category/' in notification.path:
            #    cls.process_category_notification(notification, business_data, parsed_data)
            if '/Zr6mmitc9NdqtbdQJ5cBbgszyxvr0lg6' in notification.path:
                cls.process_teletype_notification(notification)
            else:
                cls.process_generic_notification(notification)

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Ошибка обработки: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.error(f"Ошибка обработки уведомления {notification.id}: {str(err)}")

    @classmethod
    def process_balance_notification(cls, notification, business_data, parsed_data):
        """Обработка уведомления об изменении баланса"""
        try:
            logger.info(f"Обработка баланса для уведомления {notification.id}")

            # Проверяем минимально необходимые данные
            if not business_data.get('guest_id'):
                notification.status = 'error'
                notification.error_description = 'Отсутствует идентификатор гостя'
                notification.processed_at = timezone.now()
                notification.save()
                return

            # ВАША БИЗНЕС-ЛОГИКА ЗДЕСЬ
            # update_visit_history(
            #     guest_id=business_data['guest_id'],
            #     guest_name=business_data.get('guest_name', 'Неизвестно'),
            #     venue_id=business_data.get('venue_id'),
            #     balance=business_data.get('balance', 0),
            #     raw_data=parsed_data
            # )

            logger.info(
                f"Баланс гостя {business_data.get('guest_name', 'Неизвестно')} "
                f"(ID: {business_data['guest_id']}) обновлен"
            )

            # Если все успешно - меняем статус
            notification.status = 'complete'
            notification.processed_at = timezone.now()
            notification.save()

            logger.info(f"Уведомление {notification.id} успешно обработано")

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Ошибка обработки баланса: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.error(f"Ошибка обработки баланса для {notification.id}: {str(err)}")

    @classmethod
    def process_category_notification(cls, notification, business_data, parsed_data):
        """Обработка уведомления о категории гостя"""
        try:
            logger.info(f"Обработка категории для уведомления {notification.id}")

            # Проверяем минимально необходимые данные
            if not business_data.get('guest_id'):
                notification.status = 'error'
                notification.error_description = 'Отсутствует идентификатор гостя'
                notification.processed_at = timezone.now()
                notification.save()
                return

            # Определяем категорию
            balance = business_data.get('balance', 0)
            if balance > 20000:
                category = "VIP"
            elif balance > 10000:
                category = "Постоянный клиент"
            elif balance > 5000:
                category = "Активный клиент"
            else:
                category = "Новый клиент"

            # ВАША БИЗНЕС-ЛОГИКА ЗДЕСЬ
            # assign_guest_to_category(
            #     guest_id=business_data['guest_id'],
            #     category=category,
            #     balance=balance,
            #     raw_data=parsed_data
            # )

            logger.info(
                f"Гость {business_data.get('guest_name', 'Неизвестно')} "
                f"(ID: {business_data['guest_id']}) определен в категорию: {category}"
            )

            # Если все успешно - меняем статус
            notification.status = 'complete'
            notification.processed_at = timezone.now()
            notification.save()

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Ошибка обработки категории: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()
            logger.error(f"Ошибка обработки категории для {notification.id}: {str(err)}")

    @classmethod
    def process_teletype_notification(cls, notification):
        """Обработка уведомлений от Teletype"""
        try:
            logger.info(f"Обработка Teletype для уведомления {notification.id}")

            # Если все успешно - меняем статус
            notification.status = 'complete'
            notification.processed_at = timezone.now()
            notification.save()

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Ошибка обработки Teletype уведомления: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()

    @classmethod
    def process_generic_notification(cls, notification):
        """Обработка уведомлений неизвестного типа"""
        try:
            logger.warning(f"Неизвестный тип уведомления {notification.id}")

            # Просто логируем и отмечаем как завершенное
            notification.status = 'complete'
            notification.error_description = 'Неизвестный тип уведомления, данные сохранены'
            notification.processed_at = timezone.now()
            notification.save()

        except Exception as err:
            notification.status = 'error'
            notification.error_description = f"Ошибка обработки generic уведомления: {str(err)}"
            notification.processed_at = timezone.now()
            notification.save()

    @classmethod
    def process_pending_notifications(cls):
        """
        Обработка ВСЕХ уведомлений со статусом 'новый'
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

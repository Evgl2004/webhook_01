from json import dumps as json_dumps
from redis import from_url as redis_from_url
from django.conf import settings
from datetime import datetime, timezone

from main_wh.conf import app_settings

import logging
logger = logging.getLogger(__name__)


class RedisQueue:
    """Безопасный клиент для работы с Redis очередями"""

    def __init__(self):
        # Инициализация переменной для хранения подключения к Redis
        # None означает, что подключение еще не установлено
        self.redis_client = None

        # Получение имени очереди из настроек Django
        # getattr получает значение REDIS_QUEUE_NAME из settings,
        # если его нет, используется значение по умолчанию 'webhook_queue'
        self.queue_name = app_settings.REDIS_QUEUE_NAME

    def _get_connection(self):
        """
        Приватный метод для установления соединения с Redis.
        Использует ленивую инициализацию - соединение создается только при первом вызове.
        """

        # Проверка, было ли уже установлено соединение
        if self.redis_client is None:
            # Если соединения нет, пытаемся установить
            try:
                # Получение URL для подключения к Redis из настроек Django
                redis_url = app_settings.REDIS_QUEUE_URL

                # Создание клиента Redis из URL с дополнительными параметрами
                self.redis_client = redis_from_url(
                    redis_url,
                    # Автоматически декодировать ответы из bytes в строки
                    decode_responses=True,
                    # Таймаут на операции с сокетом (5 секунд)
                    socket_timeout=5,
                    # Таймаут на установку соединения (5 секунд)
                    socket_connect_timeout=5,
                    # Повторять попытку при таймауте
                    retry_on_timeout=True
                )
                # Отправка тестовой команды PING для проверки работоспособности соединения
                # Если Redis недоступен, будет выброшено исключение
                self.redis_client.ping()

            except Exception as err:
                logger.error(f"Ошибка подключения к Redis: {err}")
                # Сброс клиента в None, чтобы при следующем вызове была попытка переподключения
                self.redis_client = None
                raise
        # Возврат клиента Redis (существующего или только что созданного)
        return self.redis_client

    def send_to_business_queue(self, webhook_data):
        """
        Отправка информации об поступившем Уведомлении в очередь для бизнес-сервиса.

        Args:
            webhook_data (dict): Данные Уведомления.
        Returns:
            bool: Успешность отправки
        """
        try:
            # Получение подключения к Redis (с ленивой инициализацией)
            redis_client = self._get_connection()

            # Формирование структуры сообщения для отправки в очередь
            message = {
                # Идентификатор Уведомления из полученных данных
                'id': webhook_data.get('id'),
                'category': webhook_data.get('category'),
                'parsed_body': webhook_data.get('parsed_body', {}),
                'created_at': webhook_data.get('created_at'),
                'metadata': {
                    # Источник сообщения
                    'source': 'webhook_service',
                    # Текущее время в UTC в ISO формате
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'version': '1.0'
                }
            }

            # Отправка сообщения в очередь Redis
            # LPUSH добавляет элемент в начало списка (очереди)
            # Преобразование словаря в JSON-строку с сохранением кириллицы (ensure_ascii=False)
            queue_length = redis_client.lpush(
                self.queue_name,
                json_dumps(message, ensure_ascii=False)
            )

            logger.info(
                f"Сообщение отправлено в очередь {self.queue_name}, "
                f"ID: {webhook_data.get('id')}, "
                f"текущая длина очереди: {queue_length}"
            )
            return True

        # Обработка исключений при отправке
        except Exception as err:
            logger.error(f"Ошибка отправки в Redis очередь: {err}")
            return False

    def get_queue_stats(self):
        """
        Получение статистики очереди
        """

        try:
            # Получение подключения к Redis
            redis_client = self._get_connection()
            # Получение длины очереди (количество элементов в списке)
            # LLEN возвращает количество элементов в списке с именем queue_name
            length = redis_client.llen(self.queue_name)
            # Возврат статистики в виде словаря
            return {
                'queue_name': self.queue_name,  # Имя очереди
                'pending_messages': length  # Количество ожидающих сообщений
            }

        # Обработка исключений при получении статистики
        except Exception as err:
            logger.error(f"Ошибка получения статистики очереди: {err}")
            # Возврат статистики с нулевым количеством сообщений и информацией об ошибке
            return {
                'queue_name': self.queue_name,
                # При ошибке считаем, что сообщений нет
                'pending_messages': 0,
                'error': str(err)
            }


# Создание глобального экземпляра класса RedisQueue.
# Этот экземпляр можно импортировать в других модулях приложения.
# Используется паттерн Singleton (единственный экземпляр для всего приложения).
redis_queue = RedisQueue()

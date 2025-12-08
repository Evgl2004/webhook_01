from rest_framework_simplejwt.authentication import JWTAuthentication

# Импорт исключений JWT для обработки ошибок валидации токенов
# InvalidToken - ошибка валидации токена (истек срок, неверная подпись и т.д.)
# AuthenticationFailed - ошибка аутентификации (неверные учетные данные)
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

# Импорт модуля логирования для записи событий аутентификации
import logging
logger = logging.getLogger(__name__)


class InternalServiceJWT(JWTAuthentication):
    """
    JWT аутентификация для внутренних сервисов с расширенной валидацией claims
    Определение модифицированного класса аутентификации, наследующегося от JWTAuthentication
    Этот класс предназначен для аутентификации внутренних сервисов с дополнительными проверками
    """

    # Переопределение основного метода аутентификации Django REST Framework
    # Этот метод вызывается для каждого запроса, требующего аутентификации
    def authenticate(self, request):
        """
        Основной метод аутентификации с проверкой кастомных claims
        """
        try:
            # 1. Вызов родительского метода authenticate() из JWTAuthentication
            #    Этот метод выполняет:
            #    - Извлечение заголовка Authorization из запроса
            #    - Проверку формата "Bearer <token>"
            #    - Валидацию JWT-токена (подпись, срок действия)
            #    - Декодирование токена и получение пользователя из БД по user_id
            #    - Возвращает кортеж (user, validated_token) или None
            auth_result = super().authenticate(request)

            # Проверка: если родительский метод не вернул результат
            # Это может означать:
            # - Отсутствие заголовка Authorization
            # - Неверный формат заголовка
            # - Просроченный или некорректно подписанный токен
            if not auth_result:
                # Запись предупреждения в лог
                logger.warning("JWT токен отсутствует или неверный")
                # Возврат None, что приводит к анонимному пользователю
                return None

            # Распаковка результата аутентификации на два компонента:
            # user - объект пользователя Django, извлеченный из БД по user_id из токена
            # validated_token - декодированный и проверенный JWT-токен (словарь claims)
            user, validated_token = auth_result

            # 2. Вызов кастомного метода для дополнительной валидации claims токена
            #    Этот метод проверяет наличие и значения специфичных claims для внутренних сервисов
            self._validate_custom_claims(validated_token)

            # 3. Логирование успешной аутентификации с подробной информацией
            #    Используется f-строка для формирования информативного сообщения
            #    В лог записывается:
            #    - Имя пользователя (из объекта user)
            #    - Тип сервиса (из кастомного claim токена)
            logger.info(
                f"Успешная аутентификация внутреннего сервиса: "
                f"Пользователь: {user.username}, "
                f"Service: {validated_token.get('service_type')}"
            )

            # Возврат успешного результата аутентификации
            # Django REST Framework использует этот кортеж для установки request.user и request.auth
            return user, validated_token

        # Обработка исключения InvalidToken (возникает при проблемах с самим токеном)
        except InvalidToken as err:
            # Логирование предупреждения с текстом ошибки
            logger.warning(f"Невалидный JWT токен: {str(err)}")
            # Возврат None (пользователь не аутентифицирован)
            return None

        # Обработка исключения AuthenticationFailed (возникает в _validate_custom_claims)
        except AuthenticationFailed as err:
            # Логирование предупреждения
            logger.warning(f"Ошибка аутентификации: {str(err)}")
            # Повторный вызов исключения - оно будет обработано DRF
            # DRF вернет HTTP 401 Unauthorized с соответствующим сообщением
            raise

        # Обработка любых других непредвиденных исключений
        except Exception as err:
            # Логирование критической ошибки (уровень ERROR)
            logger.error(f"Критическая ошибка при аутентификации: {str(err)}")
            # Возврат None для предотвращения сбоя всего запроса
            return None

    # Приватный метод (по соглашению, начинается с _) для валидации кастомных claims
    # Claims - это поля полезной нагрузки (payload) JWT-токена
    def _validate_custom_claims(self, token):
        """
        Валидация кастомных claims в токене
        """
        # Словарь обязательных claims и их ожидаемых значений
        # Эти claims не являются стандартными JWT, а добавляются при генерации токена
        required_claims = {
            'service_type': 'internal_service',  # Тип сервиса должен быть 'internal_service'
            'iss': 'webhook_service',  # Издатель (issuer) токена
            'aud': 'business_service',  # Аудитория (audience) токена
        }

        # Проверка jti (JWT ID) против черного списка
        if self._is_token_blacklisted(token.get('jti')):
            raise AuthenticationFailed("Токен отозван")

        # Итерация по всем обязательным claims
        for claim_name, expected_value in required_claims.items():
            # Получение значения claim из токена
            # token - это словарь с декодированными claims
            actual_value = token.get(claim_name)

            # Проверка: присутствует ли claim в токене
            if not actual_value:
                # Если claim отсутствует - выбрасываем исключение аутентификации
                raise AuthenticationFailed(f"Отсутствует обязательный claim: {claim_name}")

            # Проверка: соответствует ли значение claim ожидаемому
            if actual_value != expected_value:
                # Если значение не совпадает - выбрасываем исключение с подробным сообщением
                raise AuthenticationFailed(
                    f"Некорректное значение claim {claim_name}: "
                    f"ожидалось '{expected_value}', получено '{actual_value}'"
                )

        # Дополнительная проверка: убедиться, что это access-токен, а не refresh-токен
        # Стандартный claim 'token_type' указывает тип токена в simplejwt
        if token.get('token_type') != 'access':
            # Если токен не access - выбрасываем исключение
            raise AuthenticationFailed("Токен должен быть access токеном")

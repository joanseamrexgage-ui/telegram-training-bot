"""
VERSION 2.0: Global Error Handling Middleware

Централизованная обработка всех ошибок в боте с:
- Логированием через loguru
- Отправкой понятных сообщений пользователю
- Интеграцией с Sentry (опционально)
- Обработкой различных типов исключений
"""

from typing import Callable, Dict, Any, Awaitable
from datetime import datetime

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Update, Message, CallbackQuery
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramNotFound,
    TelegramConflictError,
    TelegramUnauthorizedError,
    TelegramForbiddenError,
    TelegramRetryAfter,
    RestartingTelegram,
)

from utils.logger import logger

# Try to import Sentry if available
try:
    from utils.sentry_config import capture_exception_with_context
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


class ErrorHandlingMiddleware(BaseMiddleware):
    """
    Middleware для глобальной обработки ошибок

    Перехватывает все исключения, логирует их и отправляет
    пользователю понятное сообщение вместо краша бота.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Обработка события с перехватом ошибок

        Args:
            handler: Следующий обработчик
            event: Событие от Telegram
            data: Данные события

        Returns:
            Результат обработки или None при ошибке
        """

        try:
            # Выполняем обработчик
            return await handler(event, data)

        except TelegramRetryAfter as e:
            # Rate limit от Telegram - нужно подождать
            logger.warning(
                f"⚠️ Telegram Rate Limit: нужно подождать {e.retry_after} секунд"
            )
            await self._send_error_message(
                event,
                "⏳ Слишком много запросов. Пожалуйста, подождите немного."
            )
            return None

        except TelegramBadRequest as e:
            # Некорректный запрос к API
            logger.error(f"❌ Telegram Bad Request: {e}")

            # Специальная обработка для распространенных ошибок
            error_text = str(e).lower()

            if "message is not modified" in error_text:
                # Попытка отредактировать сообщение тем же текстом - игнорируем
                logger.debug("Попытка редактирования без изменений - игнорируется")
                return None

            elif "message to edit not found" in error_text:
                # Сообщение для редактирования не найдено
                logger.warning("Сообщение для редактирования не найдено")
                return None

            elif "message can't be deleted" in error_text:
                # Нельзя удалить сообщение
                logger.warning("Невозможно удалить сообщение")
                return None

            else:
                # Другие Bad Request ошибки
                await self._send_error_message(
                    event,
                    "❌ Произошла ошибка при обработке запроса. Попробуйте еще раз."
                )
                self._log_error_details(e, event, data)
                return None

        except TelegramForbiddenError as e:
            # Бот заблокирован пользователем
            logger.warning(f"⚠️ Бот заблокирован пользователем: {e}")
            # Не отправляем сообщение, так как пользователь заблокировал бота
            return None

        except TelegramUnauthorizedError as e:
            # Неавторизованный доступ (неверный токен)
            logger.critical(f"🚨 КРИТИЧНО: Неверный токен бота: {e}")
            return None

        except TelegramNotFound as e:
            # Сущность не найдена (чат, пользователь, сообщение)
            logger.warning(f"⚠️ Не найдено: {e}")
            return None

        except TelegramConflictError as e:
            # Конфликт (например, два бота с одним токеном)
            logger.critical(f"🚨 КРИТИЧНО: Конфликт Telegram: {e}")
            return None

        except RestartingTelegram:
            # Telegram перезагружается
            logger.warning("⚠️ Telegram перезагружается, повторяем позже")
            return None

        except ValueError as e:
            # Ошибка валидации данных
            logger.error(f"❌ Ошибка валидации: {e}")
            await self._send_error_message(
                event,
                "⚠️ Некорректные данные. Пожалуйста, проверьте ввод."
            )
            self._log_error_details(e, event, data)
            return None

        except KeyError as e:
            # Отсутствующий ключ в данных
            logger.error(f"❌ Отсутствующий ключ: {e}")
            await self._send_error_message(
                event,
                "❌ Ошибка обработки данных. Попробуйте начать сначала."
            )
            self._log_error_details(e, event, data)
            return None

        except Exception as e:
            # Все остальные непредвиденные ошибки
            logger.exception(f"💥 Непредвиденная ошибка: {e}")

            await self._send_error_message(
                event,
                "💥 Произошла непредвиденная ошибка.\n"
                "Попробуйте /start для перезапуска или обратитесь к администратору."
            )

            self._log_error_details(e, event, data)

            # Отправляем в Sentry если доступен
            if SENTRY_AVAILABLE:
                try:
                    user_id = self._extract_user_id(event)
                    capture_exception_with_context(
                        exception=e,
                        user_id=user_id,
                        extra={
                            "event_type": type(event).__name__,
                            "timestamp": datetime.utcnow().isoformat(),
                        }
                    )
                except Exception as sentry_error:
                    logger.error(f"Ошибка отправки в Sentry: {sentry_error}")

            return None

    async def _send_error_message(
        self,
        event: TelegramObject,
        text: str
    ) -> None:
        """
        Отправка сообщения об ошибке пользователю

        Args:
            event: Событие Telegram
            text: Текст сообщения об ошибке
        """

        try:
            if isinstance(event, Message):
                await event.answer(text)

            elif isinstance(event, CallbackQuery):
                # Для callback - показываем alert
                await event.answer(text, show_alert=True)

                # И пытаемся отправить сообщение в чат
                try:
                    await event.message.answer(text)
                except Exception:
                    pass

        except Exception as e:
            # Если не получается отправить сообщение - просто логируем
            logger.error(f"Не удалось отправить сообщение об ошибке: {e}")

    def _log_error_details(
        self,
        exception: Exception,
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> None:
        """
        Логирование деталей ошибки

        Args:
            exception: Исключение
            event: Событие Telegram
            data: Данные события
        """

        user_id = self._extract_user_id(event)
        event_type = type(event).__name__

        logger.error(
            f"Error Details:\n"
            f"  Exception: {type(exception).__name__}\n"
            f"  Message: {str(exception)}\n"
            f"  User ID: {user_id}\n"
            f"  Event Type: {event_type}\n"
            f"  Timestamp: {datetime.utcnow().isoformat()}"
        )

    def _extract_user_id(self, event: TelegramObject) -> int | None:
        """
        Извлечение user_id из события

        Args:
            event: Событие Telegram

        Returns:
            User ID или None
        """

        try:
            if hasattr(event, 'from_user') and event.from_user:
                return event.from_user.id
            elif hasattr(event, 'message') and event.message:
                if hasattr(event.message, 'from_user') and event.message.from_user:
                    return event.message.from_user.id
        except Exception:
            pass

        return None


__all__ = ["ErrorHandlingMiddleware"]

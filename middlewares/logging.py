"""
Middleware для логирования активности пользователей.

Этот модуль отвечает за:
- Логирование всех сообщений от пользователей
- Логирование всех callback запросов
- Сохранение действий пользователей в БД
- Отслеживание переходов между разделами меню
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.crud import log_user_activity
from utils.logger import logger


class LoggingMiddleware(BaseMiddleware):
    """
    Middleware для логирования действий пользователей.
    
    Записывает все действия пользователей в БД для:
    - Аналитики использования бота
    - Отслеживания популярных разделов
    - Статистики для админ-панели
    - Отладки и мониторинга
    """
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Основной метод middleware.
        
        Args:
            handler: Следующий обработчик в цепочке
            event: Событие от Telegram (Message или CallbackQuery)
            data: Словарь с данными, передаваемыми между middlewares
            
        Returns:
            Результат выполнения handler
        """
        
        # Извлекаем пользователя из события
        user = None
        action = None
        section = None
        
        if isinstance(event, Message):
            user = event.from_user
            action = "message"
            section = event.text[:50] if event.text else "media"
            
            # Логируем сообщение
            logger.info(
                f"💬 Сообщение от пользователя {user.id} (@{user.username}): "
                f"{event.text[:100] if event.text else '[медиа]'}"
            )
            
        elif isinstance(event, CallbackQuery):
            user = event.from_user
            action = "callback"
            section = event.data[:50] if event.data else "unknown"
            
            # Логируем callback
            logger.info(
                f"🔘 Callback от пользователя {user.id} (@{user.username}): "
                f"{event.data}"
            )
        
        # Если не удалось получить пользователя, пропускаем логирование
        if not user:
            return await handler(event, data)
        
        telegram_id = user.id
        
        # Получаем текущее состояние FSM (если есть)
        state_name = None
        if 'state' in data:
            state: FSMContext = data.get('state')
            if state:
                try:
                    current_state = await state.get_state()
                    if current_state:
                        state_name = current_state
                        logger.debug(f"📊 Текущее состояние FSM: {state_name}")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка получения состояния FSM: {e}")
        
        # Сохраняем активность в БД
        try:
            await log_user_activity(
                user_id=telegram_id,
                action=action,
                section=section,
                state=state_name
            )
            
            logger.debug(
                f"📝 Активность сохранена: user={telegram_id}, "
                f"action={action}, section={section}"
            )
            
        except Exception as e:
            # Логируем ошибку, но не прерываем обработку
            logger.error(
                f"❌ Ошибка сохранения активности для пользователя {telegram_id}: {e}"
            )
        
        # Выполняем handler и замеряем время выполнения
        import time
        start_time = time.time()
        
        try:
            result = await handler(event, data)
            
            # Логируем время выполнения
            execution_time = (time.time() - start_time) * 1000  # в миллисекундах
            
            if execution_time > 1000:  # Предупреждение, если обработка > 1 секунды
                logger.warning(
                    f"⏱️ Медленная обработка: {execution_time:.2f}ms "
                    f"для {action} от пользователя {telegram_id}"
                )
            else:
                logger.debug(
                    f"⚡ Обработка завершена за {execution_time:.2f}ms"
                )
            
            return result
            
        except Exception as e:
            # Логируем ошибку в handler
            logger.error(
                f"❌ Ошибка в handler для пользователя {telegram_id}: {e}",
                exc_info=True
            )
            
            # Отправляем сообщение об ошибке пользователю
            try:
                error_message = (
                    "⚠️ <b>Произошла ошибка</b>\n\n"
                    "Попробуйте повторить действие позже или вернуться в главное меню.\n"
                    "Если ошибка повторяется, обратитесь к администратору."
                )
                
                if isinstance(event, Message):
                    await event.answer(error_message)
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "⚠️ Произошла ошибка. Попробуйте позже.",
                        show_alert=True
                    )
            except Exception as notify_error:
                logger.error(f"❌ Не удалось уведомить пользователя об ошибке: {notify_error}")
            
            # Пробрасываем исключение дальше
            raise

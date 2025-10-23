"""
Middleware для авторизации и управления пользователями.

Этот модуль отвечает за:
- Автоматическую регистрацию новых пользователей
- Проверку блокировки пользователей
- Обновление времени последней активности
- Сохранение информации о пользователях в БД
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from database.crud import (
    get_user_by_telegram_id,
    create_user,
    update_user_activity,
    is_user_blocked
)
from utils.logger import logger


class AuthMiddleware(BaseMiddleware):
    """
    Middleware для авторизации пользователей.
    
    Выполняет следующие проверки и действия для каждого запроса:
    1. Извлекает информацию о пользователе из события
    2. Проверяет наличие пользователя в БД
    3. Регистрирует нового пользователя, если его нет
    4. Проверяет, не заблокирован ли пользователь
    5. Обновляет время последней активности
    6. Добавляет объект пользователя в data для использования в handlers
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
            Результат выполнения handler или None (если пользователь заблокирован)
        """
        
        # Извлекаем пользователя из события
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        # Если не удалось получить пользователя, пропускаем обработку
        if not user:
            logger.warning("⚠️ Не удалось извлечь информацию о пользователе из события")
            return await handler(event, data)
        
        telegram_id = user.id
        username = user.username
        first_name = user.first_name
        last_name = user.last_name
        
        try:
            # Проверяем, существует ли пользователь в БД
            db_user = await get_user_by_telegram_id(telegram_id)
            
            if db_user is None:
                # Новый пользователь - регистрируем
                logger.info(
                    f"👤 Новый пользователь: {telegram_id} "
                    f"(@{username}, {first_name} {last_name or ''})"
                )
                
                db_user = await create_user(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                
                logger.success(
                    f"✅ Пользователь зарегистрирован: ID={db_user.id}, "
                    f"Telegram ID={telegram_id}"
                )
            else:
                # Существующий пользователь - обновляем активность
                await update_user_activity(telegram_id)
            
            # Проверяем, не заблокирован ли пользователь
            if await is_user_blocked(telegram_id):
                logger.warning(
                    f"🚫 Попытка доступа заблокированного пользователя: "
                    f"{telegram_id} (@{username})"
                )
                
                # Отправляем сообщение о блокировке
                if isinstance(event, Message):
                    await event.answer(
                        "🚫 <b>Доступ заблокирован</b>\n\n"
                        "Ваш аккаунт был заблокирован администратором.\n"
                        "Для разблокировки обратитесь к администрации парка."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        "🚫 Доступ заблокирован администратором",
                        show_alert=True
                    )
                
                # Не передаем управление следующему handler
                return None
            
            # Добавляем пользователя в data для использования в handlers
            data['db_user'] = db_user
            data['user'] = user
            
        except Exception as e:
            logger.error(
                f"❌ Ошибка в AuthMiddleware для пользователя {telegram_id}: {e}",
                exc_info=True
            )
            # В случае ошибки БД всё равно пропускаем пользователя дальше
            # чтобы бот продолжал работать
        
        # Передаем управление следующему обработчику
        return await handler(event, data)

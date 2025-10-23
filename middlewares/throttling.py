"""
Middleware для защиты от спама (throttling/rate limiting).

Этот модуль отвечает за:
- Ограничение частоты запросов от одного пользователя
- Защиту от флуда (множественных быстрых запросов)
- Предотвращение DDoS атак на бота
- Автоматическую блокировку спамеров
"""

from typing import Callable, Dict, Any, Awaitable
import time

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from utils.logger import logger


class ThrottlingMiddleware(BaseMiddleware):
    """
    Middleware для ограничения частоты запросов.
    
    Использует in-memory словарь для отслеживания времени последнего запроса
    каждого пользователя. Для production лучше использовать Redis.
    
    Параметры по умолчанию:
    - Минимальный интервал между запросами: 2.0 секунды (VERSION 2.0)
    - Максимум предупреждений перед блокировкой: 5
    - Время блокировки: 60 секунд
    """
    
    def __init__(
        self,
        default_rate: float = 2.0,  # Минимальный интервал между запросами (сек) - VERSION 2.0
        max_warnings: int = 5,       # Максимум предупреждений
        block_duration: int = 60     # Время блокировки (сек)
    ):
        """
        Инициализация middleware.
        
        Args:
            default_rate: Минимальный интервал между запросами в секундах
            max_warnings: Количество предупреждений перед блокировкой
            block_duration: Длительность блокировки в секундах
        """
        super().__init__()
        self.default_rate = default_rate
        self.max_warnings = max_warnings
        self.block_duration = block_duration
        
        # Словари для хранения данных о пользователях
        # В production использовать Redis
        self.last_request_time: Dict[int, float] = {}
        self.warnings: Dict[int, int] = {}
        self.blocked_users: Dict[int, float] = {}  # user_id: block_end_time
    
    def _is_blocked(self, user_id: int) -> bool:
        """
        Проверяет, заблокирован ли пользователь.
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            True если пользователь заблокирован, False иначе
        """
        if user_id not in self.blocked_users:
            return False
        
        # Проверяем, не истекло ли время блокировки
        block_end_time = self.blocked_users[user_id]
        current_time = time.time()
        
        if current_time >= block_end_time:
            # Время блокировки истекло - разблокируем
            del self.blocked_users[user_id]
            self.warnings[user_id] = 0  # Сбрасываем предупреждения
            logger.info(f"🔓 Пользователь {user_id} автоматически разблокирован")
            return False
        
        return True
    
    def _block_user(self, user_id: int) -> None:
        """
        Блокирует пользователя на заданное время.
        
        Args:
            user_id: Telegram ID пользователя
        """
        block_end_time = time.time() + self.block_duration
        self.blocked_users[user_id] = block_end_time
        
        logger.warning(
            f"🚫 Пользователь {user_id} заблокирован за спам "
            f"на {self.block_duration} секунд"
        )
    
    def _check_throttle(self, user_id: int) -> tuple[bool, str]:
        """
        Проверяет, не нарушает ли пользователь лимиты.
        
        Args:
            user_id: Telegram ID пользователя
            
        Returns:
            Кортеж (allowed, message):
                - allowed: True если запрос разрешен, False если заблокирован
                - message: Сообщение для пользователя (если заблокирован)
        """
        current_time = time.time()
        
        # Проверяем, заблокирован ли пользователь
        if self._is_blocked(user_id):
            remaining_time = int(self.blocked_users[user_id] - current_time)
            message = (
                f"⏳ Вы заблокированы за частые запросы.\n"
                f"Попробуйте через {remaining_time} сек."
            )
            return False, message
        
        # Проверяем время последнего запроса
        if user_id in self.last_request_time:
            time_since_last = current_time - self.last_request_time[user_id]
            
            if time_since_last < self.default_rate:
                # Пользователь делает запросы слишком часто
                self.warnings[user_id] = self.warnings.get(user_id, 0) + 1
                warnings_count = self.warnings[user_id]
                
                logger.warning(
                    f"⚠️ Throttling: пользователь {user_id} "
                    f"(предупреждение {warnings_count}/{self.max_warnings})"
                )
                
                # Если превышен лимит предупреждений - блокируем
                if warnings_count >= self.max_warnings:
                    self._block_user(user_id)
                    message = (
                        f"🚫 Вы заблокированы за частые запросы на {self.block_duration} сек.\n"
                        f"Не отправляйте сообщения слишком быстро!"
                    )
                    return False, message
                
                # Предупреждение
                message = (
                    f"⚠️ Подождите немного между действиями.\n"
                    f"Предупреждение {warnings_count}/{self.max_warnings}"
                )
                return False, message
        
        # Обновляем время последнего запроса
        self.last_request_time[user_id] = current_time
        
        # Сбрасываем предупреждения, если пользователь ведет себя нормально
        if user_id in self.warnings and self.warnings[user_id] > 0:
            # Постепенно уменьшаем количество предупреждений
            self.warnings[user_id] = max(0, self.warnings[user_id] - 1)
        
        return True, ""
    
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
            Результат выполнения handler или None (если заблокирован)
        """
        
        # Извлекаем пользователя из события
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user
        
        # Если не удалось получить пользователя, пропускаем проверку
        if not user:
            return await handler(event, data)
        
        user_id = user.id
        
        # Проверяем throttling
        allowed, warning_message = self._check_throttle(user_id)
        
        if not allowed:
            # Запрос заблокирован - отправляем предупреждение
            try:
                if isinstance(event, Message):
                    await event.answer(warning_message)
                elif isinstance(event, CallbackQuery):
                    await event.answer(warning_message, show_alert=True)
            except Exception as e:
                logger.error(f"❌ Ошибка отправки предупреждения о throttling: {e}")
            
            # Не передаем управление следующему handler
            return None
        
        # Запрос разрешен - передаем управление дальше
        return await handler(event, data)

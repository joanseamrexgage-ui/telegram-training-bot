"""
Timeout Middleware - Prevents event loop blocking from slow handlers

HIGH-004 FIX: Enforces 30-second timeout on all handlers to prevent event loop blocking.

Security Impact:
- Prevents DoS attacks via intentionally slow handlers
- Protects event loop from unresponsive operations
- Provides visibility into slow handler performance

Usage:
    from middlewares.timeout import TimeoutMiddleware

    timeout_middleware = TimeoutMiddleware(timeout=30)
    dp.message.middleware(timeout_middleware)
    dp.callback_query.middleware(timeout_middleware)
"""

import asyncio
import time
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from utils.logger import logger


class TimeoutMiddleware(BaseMiddleware):
    """
    Enforce timeout on all handlers to prevent event loop blocking.

    Features:
    - Configurable timeout (default: 30s)
    - Automatic statistics tracking
    - User-friendly error messages
    - Detailed logging for debugging
    """

    def __init__(self, timeout: int = 30):
        """
        Initialize timeout middleware.

        Args:
            timeout: Maximum handler execution time in seconds (default: 30)
        """
        self.timeout = timeout
        self.stats = {
            "timeouts": 0,
            "total_requests": 0,
            "total_execution_time": 0.0
        }
        super().__init__()
        logger.info(f"⏱️ TimeoutMiddleware initialized with {timeout}s timeout")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Execute handler with timeout protection.

        Args:
            handler: The handler function to execute
            event: The Telegram event (Message, CallbackQuery, etc.)
            data: Additional data passed to handler

        Returns:
            Handler result or None if timeout occurred
        """
        self.stats["total_requests"] += 1
        start_time = time.time()

        # Extract handler name for logging
        handler_name = getattr(handler, '__name__', str(handler))

        # Extract user info for logging
        user_id = None
        username = None
        if hasattr(event, 'from_user') and event.from_user:
            user_id = event.from_user.id
            username = event.from_user.username

        try:
            # Execute handler with timeout
            result = await asyncio.wait_for(
                handler(event, data),
                timeout=self.timeout
            )

            execution_time = time.time() - start_time
            self.stats["total_execution_time"] += execution_time

            # Log slow handlers (>50% of timeout threshold)
            if execution_time > (self.timeout * 0.5):
                logger.warning(
                    f"⚠️ Slow handler detected: {handler_name} took {execution_time:.2f}s "
                    f"(threshold: {self.timeout}s)\n"
                    f"   User: {user_id} (@{username})\n"
                    f"   Event: {type(event).__name__}"
                )

            return result

        except asyncio.TimeoutError:
            self.stats["timeouts"] += 1
            execution_time = time.time() - start_time

            logger.error(
                f"⏱️ TIMEOUT: Handler exceeded {self.timeout}s limit\n"
                f"   Handler: {handler_name}\n"
                f"   Execution time: {execution_time:.2f}s\n"
                f"   Event: {type(event).__name__}\n"
                f"   User: {user_id} (@{username})\n"
                f"   Total timeouts: {self.stats['timeouts']}/{self.stats['total_requests']} "
                f"({self._get_timeout_rate():.1f}%)"
            )

            # Send user-friendly error message
            await self._send_timeout_message(event)

            return None

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"❌ Error in TimeoutMiddleware: {type(e).__name__}: {str(e)}\n"
                f"   Handler: {handler_name}\n"
                f"   Execution time: {execution_time:.2f}s\n"
                f"   User: {user_id} (@{username})",
                exc_info=True
            )
            raise

    async def _send_timeout_message(self, event: TelegramObject) -> None:
        """
        Send user-friendly timeout message.

        Args:
            event: The Telegram event that timed out
        """
        try:
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ <b>Время обработки превышено</b>\n\n"
                    "Запрос обрабатывается слишком долго. "
                    "Пожалуйста, попробуйте позже или обратитесь к администратору.",
                    parse_mode="HTML"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Timeout. Попробуйте еще раз через несколько секунд.",
                    show_alert=True
                )
        except Exception as e:
            logger.error(f"Failed to send timeout message: {e}")

    def _get_timeout_rate(self) -> float:
        """
        Calculate timeout rate percentage.

        Returns:
            Timeout rate as percentage (0-100)
        """
        if self.stats["total_requests"] == 0:
            return 0.0
        return (self.stats["timeouts"] / self.stats["total_requests"]) * 100

    def get_stats(self) -> Dict[str, Any]:
        """
        Get timeout statistics for monitoring.

        Returns:
            Dictionary with timeout statistics
        """
        avg_execution_time = 0.0
        if self.stats["total_requests"] > 0:
            avg_execution_time = (
                self.stats["total_execution_time"] / self.stats["total_requests"]
            )

        return {
            "total_requests": self.stats["total_requests"],
            "timeouts": self.stats["timeouts"],
            "timeout_rate": self._get_timeout_rate(),
            "timeout_threshold": self.timeout,
            "avg_execution_time": round(avg_execution_time, 3)
        }

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        self.stats = {
            "timeouts": 0,
            "total_requests": 0,
            "total_execution_time": 0.0
        }
        logger.info("⏱️ Timeout statistics reset")

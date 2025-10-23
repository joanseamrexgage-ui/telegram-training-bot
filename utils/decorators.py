"""
MINOR IMPROVEMENTS: Utility decorators for handlers

This module provides decorators for:
- Error handling in handlers
- Performance monitoring
- Activity logging
"""

import functools
import asyncio
from datetime import datetime
from typing import Callable, Any

from aiogram.types import Message, CallbackQuery
from utils.logger import logger


def error_handler(handler_name: str = "Handler"):
    """
    MINOR IMPROVEMENT: Decorator to wrap handler error-catching

    Instead of repeated try/except blocks in handlers, use this decorator
    to standardize error handling across all handlers.

    Usage:
        @router.message(Command("start"))
        @error_handler("start_command")
        async def cmd_start(message: Message):
            # handler code
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(
                    f"❌ Error in {handler_name}: {e}",
                    exc_info=True
                )

                # Try to send error message to user
                for arg in args:
                    if isinstance(arg, Message):
                        try:
                            await arg.answer(
                                "❌ Произошла ошибка при обработке команды.\n"
                                "Пожалуйста, попробуйте позже или обратитесь к администратору."
                            )
                        except Exception:
                            pass
                        break
                    elif isinstance(arg, CallbackQuery):
                        try:
                            await arg.answer(
                                "❌ Произошла ошибка",
                                show_alert=True
                            )
                        except Exception:
                            pass
                        break

                # Don't re-raise to keep bot running
                return None

        return wrapper
    return decorator


def log_handler_activity(action: str):
    """
    MINOR IMPROVEMENT: Decorator for automatic activity logging

    Automatically logs user actions when handler is called.

    Usage:
        @router.callback_query(F.data == "section_sales")
        @log_handler_activity("view_sales_section")
        async def show_sales(callback: CallbackQuery):
            # handler code
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Extract user info
            user_id = None
            username = None

            for arg in args:
                if isinstance(arg, (Message, CallbackQuery)):
                    user_id = arg.from_user.id
                    username = arg.from_user.username
                    break

            # Log the activity
            if user_id:
                logger.info(
                    f"User action | ID: {user_id} | "
                    f"Username: @{username or 'unknown'} | "
                    f"Action: {action}"
                )

            # Execute handler
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def async_background_task(func: Callable) -> Callable:
    """
    OPTIMIZATION: Decorator to run function as background task

    Use this for non-critical operations like logging that shouldn't
    block the user response.

    Usage:
        @async_background_task
        async def log_to_db(user_id: int, action: str):
            # logging code
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Create task without awaiting it
        task = asyncio.create_task(func(*args, **kwargs))

        # Add error callback
        def handle_task_exception(task_obj):
            try:
                task_obj.result()
            except Exception as e:
                logger.error(f"Background task error in {func.__name__}: {e}")

        task.add_done_callback(handle_task_exception)

        return task

    return wrapper


def measure_performance(func: Callable) -> Callable:
    """
    OPTIMIZATION: Decorator to measure handler performance

    Logs execution time of handlers to identify bottlenecks.

    Usage:
        @router.message(Command("stats"))
        @measure_performance
        async def cmd_stats(message: Message):
            # handler code
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        start_time = datetime.utcnow()

        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            duration = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.debug(f"⏱️ {func.__name__} executed in {duration:.2f}ms")

    return wrapper


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0):
    """
    OPTIMIZATION: Decorator to retry failed operations

    Useful for network operations or database queries that might fail temporarily.

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Delay between retries in seconds

    Usage:
        @retry_on_failure(max_attempts=3, delay=2.0)
        async def fetch_external_data():
            # network operation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {e}"
                        )

            raise last_exception

        return wrapper
    return decorator


__all__ = [
    "error_handler",
    "log_handler_activity",
    "async_background_task",
    "measure_performance",
    "retry_on_failure"
]

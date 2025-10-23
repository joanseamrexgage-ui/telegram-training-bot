"""
MOD-003 FIX: DatabaseMiddleware for dependency injection

This middleware provides database session to handlers through the data dict.
Handlers can access the session via data['db_session'].
"""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.database import get_db_session
from utils.logger import logger


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware for providing database session to handlers via dependency injection.

    This middleware:
    1. Creates a database session for each handler
    2. Provides it via data['db_session']
    3. Properly manages session lifecycle (commit/rollback)
    4. Ensures session is closed after handler execution
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Main middleware method.

        Args:
            handler: Next handler in the chain
            event: Event from Telegram
            data: Data dict passed between middlewares

        Returns:
            Result of handler execution
        """

        try:
            # Create a database session and provide it to the handler
            async for session in get_db_session():
                # Add session to data for handler access
                data['db_session'] = session

                try:
                    # Execute the handler with the session
                    result = await handler(event, data)

                    # If handler succeeded, commit any pending changes
                    await session.commit()

                    return result

                except Exception as e:
                    # If handler failed, rollback the transaction
                    await session.rollback()
                    logger.error(
                        f"Error in handler, rolling back database transaction: {e}",
                        exc_info=True
                    )
                    raise

        except Exception as e:
            logger.error(
                f"❌ Error in DatabaseMiddleware: {e}",
                exc_info=True
            )
            # Continue even if DB fails to keep bot operational
            return await handler(event, data)


__all__ = ["DatabaseMiddleware"]

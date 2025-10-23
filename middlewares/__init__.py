"""
Middlewares for Telegram training bot
"""

from middlewares.auth import AuthMiddleware
from middlewares.database import DatabaseMiddleware  # MOD-003: Added DatabaseMiddleware
from middlewares.logging import LoggingMiddleware
from middlewares.throttling import ThrottlingMiddleware

__all__ = [
    "AuthMiddleware",
    "DatabaseMiddleware",
    "LoggingMiddleware",
    "ThrottlingMiddleware"
]

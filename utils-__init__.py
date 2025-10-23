"""
Пакет утилит для Telegram-бота.

Содержит вспомогательные модули:
- logger.py: Настройка логирования с использованием loguru
"""

from utils.logger import logger, setup_logger, log_user_action

__all__ = [
    'logger',
    'setup_logger',
    'log_user_action',
]
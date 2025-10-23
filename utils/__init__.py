"""
Пакет утилит для Telegram-бота.

Содержит вспомогательные модули:
- logger.py: Настройка логирования с использованием loguru
- json_loader.py: MOD-005 - Безопасная загрузка JSON с Pydantic валидацией
"""

from utils.logger import logger, setup_logger, log_user_action
from utils.json_loader import load_json_content, validate_json_structure, clear_json_cache, SafeDict

__all__ = [
    'logger',
    'setup_logger',
    'log_user_action',
    'load_json_content',
    'validate_json_structure',
    'clear_json_cache',
    'SafeDict',
]
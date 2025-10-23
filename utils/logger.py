"""
VERSION 2.0: Настройка системы логирования с использованием Loguru

Конфигурация для production:
- Ротация логов при достижении 10 MB
- Хранение логов в течение 7 дней
- Сжатие старых файлов в ZIP
- Асинхронная запись для производительности
"""

from loguru import logger
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    log_level: str = "INFO",
    log_dir: Optional[Path] = None,
    enable_console: bool = True,
    enable_file: bool = True
) -> None:
    """
    Настройка системы логирования с использованием Loguru
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Директория для сохранения логов
        enable_console: Включить вывод в консоль
        enable_file: Включить запись в файл
    """
    # Удаляем стандартный обработчик
    logger.remove()
    
    # Форматы для разных типов вывода
    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )
    
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss} | "
        "{level: <8} | "
        "{name}:{function}:{line} | "
        "{message}"
    )
    
    # Добавляем вывод в консоль
    if enable_console:
        logger.add(
            sys.stderr,
            format=console_format,
            level=log_level,
            colorize=True,
            enqueue=True
        )
    
    # Добавляем запись в файлы
    if enable_file and log_dir:
        # Создаем директорию для логов если её нет
        log_dir = Path(log_dir) if not isinstance(log_dir, Path) else log_dir
        log_dir.mkdir(exist_ok=True)
        
        # Основной лог-файл с ротацией (VERSION 2.0)
        logger.add(
            log_dir / "bot.log",
            format=file_format,
            level=log_level,
            rotation="10 MB",  # VERSION 2.0: Ротация при 10 MB
            retention="7 days",  # VERSION 2.0: Хранение 7 дней
            compression="zip",  # Сжимаем старые файлы
            backtrace=True,  # Полная трассировка ошибок
            diagnose=True,  # Диагностическая информация
            enqueue=True  # Асинхронная запись
        )
        
        # Отдельный файл для ошибок (VERSION 2.0)
        logger.add(
            log_dir / "errors.log",
            format=file_format,
            level="ERROR",
            rotation="10 MB",  # VERSION 2.0: Ротация при 10 MB
            retention="7 days",  # VERSION 2.0: Хранение 7 дней
            compression="zip",
            backtrace=True,
            diagnose=True,
            enqueue=True
        )
        
        # Критические ошибки в отдельный файл
        logger.add(
            log_dir / "critical.log",
            format=file_format,
            level="CRITICAL",
            rotation="100 MB",  # Ротация по размеру
            retention="1 year",
            backtrace=True,
            diagnose=True,
            enqueue=True
        )
    
    logger.info(f"Система логирования инициализирована. Уровень: {log_level}")
    
    # Добавляем перехват стандартных логгеров Python
    logger.add(
        lambda msg: None,  # Пустой обработчик для перехвата
        filter=lambda record: record["level"].no >= logger.level(log_level).no
    )


def log_user_action(
    user_id: int,
    username: Optional[str],
    action: str,
    details: Optional[dict] = None
) -> None:
    """
    Логирование действий пользователя
    
    Args:
        user_id: Telegram ID пользователя
        username: Username пользователя
        action: Действие (например, "button_clicked", "command_used")
        details: Дополнительная информация
    """
    logger.info(
        f"User action | "
        f"ID: {user_id} | "
        f"Username: @{username or 'unknown'} | "
        f"Action: {action} | "
        f"Details: {details or {}}"
    )


def log_error_with_context(
    error: Exception,
    user_id: Optional[int] = None,
    context: Optional[dict] = None
) -> None:
    """
    Логирование ошибок с контекстом
    
    Args:
        error: Объект исключения
        user_id: ID пользователя (если применимо)
        context: Дополнительный контекст
    """
    logger.error(
        f"Error occurred | "
        f"Type: {type(error).__name__} | "
        f"User ID: {user_id or 'N/A'} | "
        f"Context: {context or {}} | "
        f"Error: {str(error)}",
        exc_info=True
    )


def log_admin_action(
    admin_id: int,
    action: str,
    target: Optional[str] = None,
    details: Optional[dict] = None
) -> None:
    """
    Логирование действий администраторов
    
    Args:
        admin_id: Telegram ID администратора
        action: Действие администратора
        target: Цель действия
        details: Дополнительные детали
    """
    logger.warning(
        f"Admin action | "
        f"Admin ID: {admin_id} | "
        f"Action: {action} | "
        f"Target: {target or 'N/A'} | "
        f"Details: {details or {}}"
    )


def log_database_operation(
    operation: str,
    model: str,
    success: bool,
    duration_ms: Optional[float] = None,
    details: Optional[dict] = None
) -> None:
    """
    Логирование операций с базой данных
    
    Args:
        operation: Тип операции (SELECT, INSERT, UPDATE, DELETE)
        model: Название модели
        success: Успешность операции
        duration_ms: Длительность в миллисекундах
        details: Дополнительные детали
    """
    level = "DEBUG" if success else "ERROR"
    message = (
        f"DB Operation | "
        f"Type: {operation} | "
        f"Model: {model} | "
        f"Success: {success}"
    )
    
    if duration_ms is not None:
        message += f" | Duration: {duration_ms:.2f}ms"
    
    if details:
        message += f" | Details: {details}"
    
    logger.log(level, message)


def log_bot_event(event_type: str, details: Optional[dict] = None) -> None:
    """
    Логирование событий бота
    
    Args:
        event_type: Тип события (start, stop, restart, etc.)
        details: Дополнительные детали
    """
    logger.info(f"Bot event: {event_type} | Details: {details or {}}")


# Экспорт logger для использования в других модулях
__all__ = [
    "logger",
    "setup_logger",
    "log_user_action",
    "log_error_with_context",
    "log_admin_action",
    "log_database_operation",
    "log_bot_event"
]

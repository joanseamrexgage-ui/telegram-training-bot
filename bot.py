"""
Главный файл запуска Telegram-бота для обучения сотрудников.

Этот модуль является точкой входа в приложение. Он отвечает за:
- Инициализацию бота и диспетчера
- Регистрацию всех handlers и middlewares
- Настройку базы данных
- Запуск polling
"""

import asyncio
import sys
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

# Добавляем корневую директорию проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from database.database import init_db, close_db
from handlers import start, general_info, sales, sport, admin, common
from middlewares.auth import AuthMiddleware
from middlewares.logging import LoggingMiddleware
from middlewares.throttling import ThrottlingMiddleware
from middlewares.errors import ErrorHandlingMiddleware  # VERSION 2.0
from utils.logger import logger
# PRODUCTION MONITORING: Sentry integration for error tracking
from utils.sentry_config import init_sentry


async def main():
    """
    Главная функция запуска бота.
    
    Выполняет следующие действия:
    1. Загружает конфигурацию из .env
    2. Инициализирует базу данных
    3. Создает экземпляры Bot и Dispatcher
    4. Регистрирует middlewares
    5. Регистрирует handlers
    6. Запускает polling
    """
    
    logger.info("🚀 Запуск бота для обучения сотрудников...")

    # PRODUCTION MONITORING: Initialize Sentry for error tracking
    init_sentry(
        enable_performance=True,
        enable_profiling=False,
        traces_sample_rate=0.1,  # Sample 10% of transactions
        profiles_sample_rate=0.0  # Disable profiling by default
    )

    # Загружаем конфигурацию
    try:
        config = load_config()
        logger.info("✅ Конфигурация загружена успешно")
    except Exception as e:
        logger.critical(f"❌ Ошибка загрузки конфигурации: {e}")
        sys.exit(1)
    
    # Инициализируем базу данных
    # CRIT-002 FIX: Always pass config vars to init_db()
    try:
        await init_db(
            database_url=config.db.url,
            echo=config.db.echo
        )
        logger.info("✅ База данных инициализирована")
    except Exception as e:
        logger.critical(f"❌ Ошибка инициализации базы данных: {e}")
        sys.exit(1)
    
    # Создаем экземпляр бота с настройками по умолчанию
    bot = Bot(
        token=config.tg_bot.token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML  # Используем HTML для форматирования
        )
    )
    
    # Создаем диспетчер с FSM хранилищем в памяти
    dp = Dispatcher(storage=MemoryStorage())
    
    # Регистрируем middlewares (порядок важен!)
    # 1. Throttling - защита от спама (первым, чтобы блокировать раньше)
    dp.message.middleware(ThrottlingMiddleware())
    dp.callback_query.middleware(ThrottlingMiddleware())

    # 2. Auth - авторизация и сохранение пользователей
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # 3. Error Handling - глобальная обработка ошибок (VERSION 2.0)
    dp.message.middleware(ErrorHandlingMiddleware())
    dp.callback_query.middleware(ErrorHandlingMiddleware())

    # 4. Logging - логирование действий (последним, чтобы логировать все)
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())

    logger.info("✅ Middlewares зарегистрированы")
    
    # Регистрируем handlers
    # Порядок регистрации определяет приоритет обработки
    dp.include_router(start.router)
    dp.include_router(general_info.router)
    dp.include_router(sales.router)
    dp.include_router(sport.router)
    dp.include_router(admin.router)
    dp.include_router(common.router)  # Общие handlers (назад, помощь) - ПОСЛЕДНИМИ!
    
    logger.info("✅ Handlers зарегистрированы")

    # VERSION 2.0: Глобальный обработчик ошибок
    @dp.errors()
    async def global_error_handler(event, exception):
        """
        Глобальный обработчик непойманных ошибок

        Срабатывает, когда ошибка не была обработана middleware или handler.
        Логирует ошибку и отправляет в Sentry.
        """
        from aiogram.types import Update, ErrorEvent

        logger.exception(
            f"💥 Глобальная ошибка в обработчике:\n"
            f"  Тип: {type(exception).__name__}\n"
            f"  Сообщение: {str(exception)}\n"
            f"  Update: {event.update if hasattr(event, 'update') else 'N/A'}"
        )

        # Отправляем в Sentry если доступен
        try:
            from utils.sentry_config import capture_exception_with_context

            # Извлекаем user_id если возможно
            user_id = None
            if hasattr(event, 'update') and isinstance(event.update, Update):
                if event.update.message and event.update.message.from_user:
                    user_id = event.update.message.from_user.id
                elif event.update.callback_query and event.update.callback_query.from_user:
                    user_id = event.update.callback_query.from_user.id

            capture_exception_with_context(
                exception=exception,
                user_id=user_id,
                extra={
                    "event_type": type(event).__name__,
                    "update_id": event.update.update_id if hasattr(event, 'update') else None,
                }
            )
        except Exception as sentry_error:
            logger.error(f"Ошибка отправки в Sentry: {sentry_error}")

        return True  # Помечаем ошибку как обработанную

    logger.info("✅ Глобальный обработчик ошибок зарегистрирован")

    # Информация о боте
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Бот запущен: @{bot_info.username}")
        logger.info(f"   ID: {bot_info.id}")
        logger.info(f"   Имя: {bot_info.first_name}")
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о боте: {e}")
    
    # Пропускаем накопленные обновления
    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("✅ Накопленные обновления пропущены")
    
    logger.info("=" * 50)
    logger.info("🤖 БОТ УСПЕШНО ЗАПУЩЕН И ГОТОВ К РАБОТЕ")
    logger.info("=" * 50)
    
    try:
        # Запускаем polling (бот начинает получать обновления)
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    except Exception as e:
        logger.critical(f"❌ Критическая ошибка во время работы бота: {e}")
    finally:
        # Закрываем соединения при остановке
        logger.info("🛑 Остановка бота...")
        await close_db()
        await bot.session.close()
        logger.info("✅ Бот остановлен, соединения закрыты")


if __name__ == "__main__":
    """
    Точка входа при запуске скрипта напрямую.
    Использует asyncio.run() для запуска асинхронной главной функции.
    """
    try:
        # Запускаем асинхронную главную функцию
        asyncio.run(main())
    except KeyboardInterrupt:
        # Обрабатываем Ctrl+C для корректной остановки
        logger.info("⚠️ Получен сигнал остановки (Ctrl+C)")
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        # Ловим любые неожиданные ошибки
        logger.critical(f"💥 Необработанная ошибка: {e}", exc_info=True)
        sys.exit(1)

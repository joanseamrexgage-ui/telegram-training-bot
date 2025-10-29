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
from aiogram.fsm.storage.redis import RedisStorage, DefaultKeyBuilder
from redis.asyncio import Redis

# BLOCKER-001: Redis Sentinel HA support
from utils.redis_manager import init_redis_manager, RedisSentinelManager

# BLOCKER-002 FIX: Redis-backed password attempt tracking
from utils.auth_security import init_auth_security

# Добавляем корневую директорию проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from database.database import init_db, close_db
from handlers import start, general_info, sales, sport, admin, common
from middlewares.auth import AuthMiddleware
from middlewares.logging_v2 import AsyncLoggingMiddleware  # CRIT-004 FIX: v2.0
from middlewares.throttling_v2 import create_redis_throttling, RateLimitConfig  # CRIT-002 FIX: v2.0
from middlewares.errors import ErrorHandlingMiddleware  # VERSION 2.0
from middlewares.timeout import TimeoutMiddleware  # HIGH-004 FIX: Timeout protection
from middlewares.input_sanitizer import InputSanitizerMiddleware  # TASK 1.3: Input validation
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
    # ARCH-003 FIX: Connection pooling configuration
    try:
        await init_db(
            database_url=config.db.url,
            echo=config.db.echo,
            pool_size=config.db.pool_size,
            max_overflow=config.db.max_overflow,
            pool_timeout=config.db.pool_timeout,
            pool_recycle=config.db.pool_recycle
        )
        logger.info("✅ База данных инициализирована с connection pooling")
    except Exception as e:
        logger.critical(f"❌ Ошибка инициализации базы данных: {e}")
        sys.exit(1)
    
    # Создаем экземпляр бота с настройками по умолчанию
    bot = Bot(
        token=config.tg_bot.token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML  # Используем HTML для форматирование
        )
    )

    # BLOCKER-001 FIX: Redis FSM Storage с Sentinel HA support
    storage = None
    redis_manager = None

    try:
        if config.redis.is_sentinel_mode:
            # BLOCKER-001: Use Sentinel HA cluster
            logger.info(
                f"🔄 Initializing Redis Sentinel HA cluster...\n"
                f"   Nodes: {config.redis.sentinel_nodes}\n"
                f"   Master: {config.redis.master_name}"
            )

            redis_manager = await init_redis_manager(
                sentinels=config.redis.sentinel_nodes,
                master_name=config.redis.master_name,
                db=config.redis.fsm_db,
                socket_timeout=5.0,
                max_connections=50,
                enable_circuit_breaker=True
            )

            # Get Redis connection from Sentinel manager
            redis_fsm = await redis_manager.get_redis()

            storage = RedisStorage(
                redis=redis_fsm,
                key_builder=DefaultKeyBuilder(with_destiny=True)
            )
            logger.info(
                f"✅ Redis FSM Storage инициализирован через Sentinel HA\n"
                f"   Master: {config.redis.master_name}\n"
                f"   Sentinels: {len(config.redis.sentinel_nodes)} nodes\n"
                f"   Circuit Breaker: ENABLED"
            )

            # BLOCKER-002 FIX: Initialize AuthSecurity with Redis backend
            init_auth_security(redis_fsm)
            logger.info("✅ AuthSecurity initialized with Redis Sentinel backend")

        else:
            # Simple Redis mode (development)
            redis_fsm = Redis.from_url(
                f"{config.redis.url}/{config.redis.fsm_db}",
                decode_responses=True
            )
            # Test connection
            await redis_fsm.ping()

            storage = RedisStorage(
                redis=redis_fsm,
                key_builder=DefaultKeyBuilder(with_destiny=True)
            )
            logger.info(
                f"✅ Redis FSM Storage инициализирован (simple mode): {config.redis.url}/{config.redis.fsm_db}"
            )

            # BLOCKER-002 FIX: Initialize AuthSecurity with Redis backend
            init_auth_security(redis_fsm)
            logger.info("✅ AuthSecurity initialized with Redis backend")

    except Exception as e:
        logger.error(
            f"⚠️ Redis недоступен: {e}\n"
            f"   Fallback на MemoryStorage (состояния будут теряться при рестарте!)"
        )
        storage = MemoryStorage()

    # Создаем диспетчер с Redis FSM хранилищем
    dp = Dispatcher(storage=storage)
    
    # ARCH-001: КРИТИЧЕСКИЙ ПОРЯДОК MIDDLEWARES
    # ========================================
    # Порядок выполнения КРИТИЧЕСКИ ВАЖЕН для безопасности и производительности!
    #
    # Execution Order (outer → inner):
    # 0. Timeout         → Предотвращает зависание event loop (защита от DoS)
    # 1. Throttling      → Блокирует спам ДО любой обработки (защита ресурсов)
    # 2. InputSanitizer  → Очищает пользовательский ввод (защита от XSS/injection)
    # 3. Auth            → Аутентифицирует пользователя (требует DB)
    # 4. ErrorHandling   → Ловит ошибки из handlers и внутренних middleware
    # 5. Logging         → Логирует УСПЕШНЫЕ запросы (после всех проверок)
    #
    # НИКОГДА НЕ МЕНЯЙТЕ ПОРЯДОК БЕЗ ПОЛНОГО ПОНИМАНИЯ ПОСЛЕДСТВИЙ!
    # См. tests/test_middleware_order.py для автоматической проверки

    # 0. HIGH-004 FIX: Timeout Protection (MUST BE FIRST!)
    timeout_middleware = TimeoutMiddleware(timeout=30)
    dp.message.middleware(timeout_middleware)
    dp.callback_query.middleware(timeout_middleware)
    logger.info("✅ Timeout middleware registered (30s timeout)")

    # 1. BLOCKER-001 & CRIT-002 & SEC-002 FIX: Redis Token Bucket Throttling с Sentinel support
    try:
        if config.redis.is_sentinel_mode:
            # BLOCKER-001: Use Sentinel HA cluster for throttling
            from middlewares.throttling_v2 import ThrottlingMiddlewareV2, RateLimitConfig

            # Initialize separate Sentinel manager for throttling (different DB)
            throttle_manager = await init_redis_manager(
                sentinels=config.redis.sentinel_nodes,
                master_name=config.redis.master_name,
                db=config.redis.throttle_db,
                socket_timeout=5.0,
                max_connections=50,
                enable_circuit_breaker=True
            )

            # Get Redis connection from Sentinel manager
            throttle_redis = await throttle_manager.get_redis()

            # Create middleware with Sentinel-backed Redis
            # UX-001 FIX: "Invisible" throttling - user-friendly rate limits
            throttle_config = RateLimitConfig(
                max_tokens=15,              # Burst: 15 requests (was: 5)
                refill_rate=2.0,           # Recovery: 2 req/sec (was: 0.5)
                violation_threshold=8,      # Warnings: 8 (was: 3)
                block_duration=10          # Block: 10 sec (was: 60)
            )

            throttling_middleware = ThrottlingMiddlewareV2(
                redis=throttle_redis,
                config=throttle_config,
                admin_ids=config.tg_bot.admin_ids  # UX-001: Admins bypass rate limiting
            )

            dp.message.middleware(throttling_middleware)
            dp.callback_query.middleware(throttling_middleware)

            logger.info(
                f"✅ Redis Throttling Middleware активирован через Sentinel HA\n"
                f"   Master: {config.redis.master_name}\n"
                f"   Circuit Breaker: ENABLED"
            )

        else:
            # Simple Redis mode (development)
            # UX-001 FIX: "Invisible" throttling - user-friendly rate limits
            throttling_middleware = await create_redis_throttling(
                redis_url=f"{config.redis.url}/{config.redis.throttle_db}",
                max_tokens=15,              # Burst: 15 requests (was: 5)
                refill_rate=2.0,           # Recovery: 2 req/sec (was: 0.5)
                violation_threshold=8,      # Warnings: 8 (was: 3)
                block_duration=10,         # Block: 10 sec (was: 60)
                admin_ids=config.tg_bot.admin_ids  # UX-001: Admins bypass rate limiting
            )
            dp.message.middleware(throttling_middleware)
            dp.callback_query.middleware(throttling_middleware)
            logger.info("✅ Redis Throttling Middleware активирован (simple mode)")

    except Exception as e:
        logger.error(
            f"⚠️ Throttling Middleware НЕДОСТУПЕН: {e}\n"
            f"   Бот НЕ защищен от спама!"
        )

    # 2. TASK 1.3: Input Sanitizer Middleware - автоматическая очистка ввода
    input_sanitizer = InputSanitizerMiddleware(
        max_text_length=4096,      # Telegram message limit
        max_callback_length=64,    # Callback data limit
        enable_logging=True,
        enable_stats=True
    )
    dp.message.middleware(input_sanitizer)
    dp.callback_query.middleware(input_sanitizer)
    logger.info("✅ Input Sanitizer Middleware активирован (XSS/injection protection)")

    # 3. Auth Middleware - авторизация пользователей
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # 4. Error Handling Middleware - обработка ошибок
    dp.message.middleware(ErrorHandlingMiddleware())
    dp.callback_query.middleware(ErrorHandlingMiddleware())

    # 5. BLOCKER-004 & CRIT-004 FIX: Async Logging Middleware (non-blocking + memory safe)
    async_logging = AsyncLoggingMiddleware(
        enable_performance_tracking=True,
        max_concurrent_tasks=500,  # BLOCKER-004: Prevent unbounded task growth
        cleanup_interval=60  # Cleanup every 60 seconds
    )
    dp.message.middleware(async_logging)
    dp.callback_query.middleware(async_logging)

    logger.info("✅ All Production Middlewares зарегистрированы (v3.0 Enterprise)")
    
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

        # BLOCKER-004: Shutdown async logging middleware (cleanup tasks)
        try:
            await async_logging.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down logging middleware: {e}")

        # BLOCKER-001: Close Redis Sentinel managers if initialized
        if redis_manager:
            try:
                await redis_manager.close()
                logger.info("✅ Redis Sentinel FSM manager closed")
            except Exception as e:
                logger.error(f"Error closing Redis FSM manager: {e}")

        # Note: throttle_manager is in different scope, handled by middleware cleanup

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

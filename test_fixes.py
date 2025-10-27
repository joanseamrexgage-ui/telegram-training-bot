#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправлений базы данных и Redis
"""

import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию проекта в путь для импорта
sys.path.insert(0, str(Path(__file__).parent))

from config import load_config
from database.database import init_db, close_db
from utils.logger import logger
import redis.asyncio as redis


async def test_database():
    """Тест базы данных"""
    logger.info("🧪 Тестирование базы данных...")
    
    try:
        config = load_config()
        logger.info(f"✅ Конфигурация загружена: {config.db.url}")
        
        await init_db(
            database_url=config.db.url,
            echo=config.db.echo,
            pool_size=config.db.pool_size,
            max_overflow=config.db.max_overflow,
            pool_timeout=config.db.pool_timeout,
            pool_recycle=config.db.pool_recycle
        )
        logger.info("✅ База данных успешно инициализирована!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Ошибка базы данных: {e}")
        return False
    finally:
        try:
            await close_db()
        except:
            pass


async def test_redis():
    """Тест Redis"""
    logger.info("🧪 Тестирование Redis...")
    
    try:
        # Пытаемся подключиться к Redis
        r = redis.from_url("redis://localhost:6379/0")
        await r.ping()
        logger.info("✅ Redis успешно подключен!")
        await r.close()
        return True
        
    except Exception as e:
        logger.warning(f"⚠️ Redis недоступен: {e}")
        logger.info("💡 Бот будет работать в режиме MemoryStorage + Memory Throttling")
        return False


async def main():
    """Главная функция тестирования"""
    logger.info("🚀 Запуск тестов исправлений...")
    
    # Тест базы данных
    db_ok = await test_database()
    
    # Тест Redis
    redis_ok = await test_redis()
    
    # Результаты
    logger.info("📊 Результаты тестирования:")
    logger.info(f"   База данных: {'✅ OK' if db_ok else '❌ FAILED'}")
    logger.info(f"   Redis: {'✅ OK' if redis_ok else '⚠️ FALLBACK'}")
    
    if db_ok:
        logger.info("🎉 Все критические исправления работают!")
        logger.info("💡 Бот готов к запуску (даже без Redis)")
    else:
        logger.error("❌ Остались проблемы с базой данных")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("🛑 Тест прерван пользователем")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        sys.exit(1)
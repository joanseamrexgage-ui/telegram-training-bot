"""
Инициализация базы данных и создание сессий
"""

from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    async_sessionmaker, 
    AsyncSession,
    AsyncEngine
)
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from database.models import Base
from utils.logger import logger


class DatabaseManager:
    """Менеджер для работы с базой данных"""

    def __init__(
        self,
        database_url: str,
        echo: bool = False,
        pool_size: int = 20,
        max_overflow: int = 30,
        pool_timeout: int = 30,
        pool_recycle: int = 3600
    ):
        """
        Инициализация менеджера БД

        Args:
            database_url: URL подключения к БД
            echo: Выводить SQL запросы в лог
            pool_size: Размер пула соединений (ARCH-003)
            max_overflow: Максимальное количество дополнительных соединений
            pool_timeout: Таймаут ожидания свободного соединения (сек)
            pool_recycle: Время переиспользования соединения (сек)
        """
        self.database_url = database_url
        self.echo = echo
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.engine: Optional[AsyncEngine] = None
        self.async_session_maker: Optional[async_sessionmaker] = None
        
    async def init(self) -> None:
        """Инициализация подключения к БД"""
        try:
            # Специальные настройки для SQLite
            if "sqlite" in self.database_url.lower():
                # Для SQLite используем NullPool чтобы избежать проблем с потоками
                self.engine = create_async_engine(
                    self.database_url,
                    echo=self.echo,
                    future=True,
                    poolclass=NullPool,
                    connect_args={"check_same_thread": False}
                )
            else:
                # ARCH-003 FIX: PostgreSQL с production connection pooling
                self.engine = create_async_engine(
                    self.database_url,
                    echo=self.echo,
                    future=True,
                    pool_size=self.pool_size,
                    max_overflow=self.max_overflow,
                    pool_timeout=self.pool_timeout,
                    pool_pre_ping=True,  # Проверка соединения перед использованием
                    pool_recycle=self.pool_recycle  # Обновление соединений
                )
            
            # Создаем фабрику сессий
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False,  # Важно для асинхронной работы
                autoflush=False,
                autocommit=False
            )
            
            # Создаем таблицы если их нет
            await self.create_tables()
            
            # Проверяем подключение
            await self.check_connection()
            
            logger.info(f"База данных успешно инициализирована: {self._safe_url}")
            
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")
            raise
    
    async def create_tables(self) -> None:
        """Создание всех таблиц в БД"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Таблицы базы данных созданы/проверены")
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц: {e}")
            raise
    
    async def drop_tables(self) -> None:
        """Удаление всех таблиц (ОСТОРОЖНО!)"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.warning("Все таблицы базы данных удалены!")
        except Exception as e:
            logger.error(f"Ошибка при удалении таблиц: {e}")
            raise
    
    async def check_connection(self) -> bool:
        """Проверка соединения с БД"""
        try:
            async with self.engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                row = result.fetchone()  # ✅ fetchone() - синхронная операция
            return True
        except Exception as e:
            logger.error(f"Не удалось подключиться к базе данных: {e}")
            return False
    
    async def close(self) -> None:
        """Закрытие соединения с БД"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Соединение с базой данных закрыто")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Контекстный менеджер для получения сессии
        
        Yields:
            AsyncSession: Асинхронная сессия SQLAlchemy
        """
        if not self.async_session_maker:
            raise RuntimeError("База данных не инициализирована. Вызовите init() сначала.")
        
        async with self.async_session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Ошибка в транзакции БД: {e}")
                raise
            finally:
                await session.close()
    
    async def execute_raw(self, query: str, params: Optional[dict] = None) -> any:
        """
        Выполнение сырого SQL запроса
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            
        Returns:
            Результат запроса
        """
        async with self.get_session() as session:
            result = await session.execute(text(query), params or {})
            return result.fetchall()
    
    @property
    def _safe_url(self) -> str:
        """URL БД без пароля для логов"""
        if "postgresql" in self.database_url:
            # Скрываем пароль в PostgreSQL URL
            parts = self.database_url.split("@")
            if len(parts) > 1:
                user_pass = parts[0].split("//")[1]
                user = user_pass.split(":")[0] if ":" in user_pass else user_pass
                return f"postgresql://{user}:***@{parts[1]}"
        return self.database_url


# Глобальный экземпляр менеджера БД
db_manager: Optional[DatabaseManager] = None


async def init_db(
    database_url: str,
    echo: bool = False,
    pool_size: int = 20,
    max_overflow: int = 30,
    pool_timeout: int = 30,
    pool_recycle: int = 3600
) -> DatabaseManager:
    """
    Инициализация глобального менеджера БД

    Args:
        database_url: URL подключения к БД
        echo: Выводить SQL запросы в лог
        pool_size: Размер пула соединений (ARCH-003)
        max_overflow: Максимальное количество дополнительных соединений
        pool_timeout: Таймаут ожидания свободного соединения (сек)
        pool_recycle: Время переиспользования соединения (сек)

    Returns:
        DatabaseManager: Инициализированный менеджер БД
    """
    global db_manager

    db_manager = DatabaseManager(
        database_url=database_url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle
    )
    await db_manager.init()

    return db_manager


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Получение сессии из глобального менеджера
    
    Yields:
        AsyncSession: Асинхронная сессия SQLAlchemy
    """
    if not db_manager:
        raise RuntimeError("База данных не инициализирована. Вызовите init_db() сначала.")
    
    async with db_manager.get_session() as session:
        yield session


async def close_db() -> None:
    """Закрытие глобального соединения с БД"""
    global db_manager
    
    if db_manager:
        await db_manager.close()
        db_manager = None
        logger.info("Глобальное соединение с БД закрыто")


# Вспомогательные функции для работы с БД
async def check_db_health() -> dict:
    """
    Проверка состояния БД
    
    Returns:
        dict: Информация о состоянии БД
    """
    if not db_manager:
        return {"status": "error", "message": "База данных не инициализирована"}
    
    try:
        is_connected = await db_manager.check_connection()
        
        if not is_connected:
            return {"status": "error", "message": "Нет соединения с БД"}
        
        # Получаем статистику
        async with db_manager.get_session() as session:
            # Подсчет пользователей
            from database.models import User
            from sqlalchemy import select, func
            
            users_count = await session.scalar(
                select(func.count()).select_from(User)
            )
            
            return {
                "status": "ok",
                "message": "База данных работает нормально",
                "stats": {
                    "users_count": users_count,
                    "engine_pool_size": getattr(db_manager.engine.pool, "size", None),
                    "engine_pool_checked_out": getattr(db_manager.engine.pool, "checked_out", None)
                }
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


__all__ = [
    "DatabaseManager",
    "db_manager",
    "init_db",
    "get_db_session",
    "close_db",
    "check_db_health"
]

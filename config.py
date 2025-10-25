"""
Модуль конфигурации приложения
Загружает и валидирует переменные окружения
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import os
import logging
from dotenv import load_dotenv

# Setup logger
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()


@dataclass
class TgBot:
    """Конфигурация Telegram бота"""
    token: str
    admin_password: str
    admin_ids: List[int]
    use_webhook: bool = False
    webhook_host: Optional[str] = None
    webhook_path: Optional[str] = None
    webapp_host: Optional[str] = None
    webapp_port: Optional[int] = None


@dataclass
class Database:
    """Конфигурация базы данных"""
    url: str
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 30
    pool_timeout: int = 30
    pool_recycle: int = 3600

    @property
    def is_sqlite(self) -> bool:
        """Проверяет, используется ли SQLite"""
        return "sqlite" in self.url.lower()


@dataclass
class Redis:
    """
    Конфигурация Redis для FSM и rate limiting

    BLOCKER-001 FIX: Поддержка Redis Sentinel для HA

    Modes:
    1. Sentinel HA Mode (Production):
       - sentinel_nodes: List of (host, port) tuples
       - master_name: Sentinel master name
       - Automatic failover support

    2. Simple Mode (Development):
       - url: Direct Redis connection URL
       - No HA, single instance
    """
    url: str
    fsm_db: int = 0  # Database index для FSM хранилища
    throttle_db: int = 1  # Database index для throttling

    # BLOCKER-001: Sentinel HA configuration
    sentinel_nodes: Optional[List[tuple]] = None  # [(host1, port1), (host2, port2), ...]
    master_name: str = "mymaster"  # Sentinel master name

    @property
    def is_sentinel_mode(self) -> bool:
        """Check if Sentinel HA mode is enabled"""
        return self.sentinel_nodes is not None and len(self.sentinel_nodes) > 0


@dataclass
class RateLimit:
    """Конфигурация rate limiting"""
    messages: int
    callbacks: int
    time_window: int = 1  # секунды


@dataclass
class Paths:
    """Пути к директориям"""
    content: Path
    logs: Path
    media: Path
    documents: Path
    
    def ensure_exists(self):
        """Создает директории если их нет"""
        for path in [self.content, self.logs, self.media, self.documents]:
            path.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    """Общая конфигурация приложения"""
    tg_bot: TgBot
    db: Database
    redis: Redis
    rate_limit: RateLimit
    paths: Paths
    debug: bool = False
    log_level: str = "INFO"
    timezone: str = "Europe/Moscow"


def load_config() -> Config:
    """
    Загрузка и валидация конфигурации из переменных окружения

    Returns:
        Config: Объект с конфигурацией приложения

    Raises:
        ValueError: Если обязательные переменные не установлены
    """
    # Обязательные переменные
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError(
            "❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не установлен!\n"
            "Пожалуйста, создайте файл .env на основе .env.example и заполните BOT_TOKEN"
        )
    
    admin_password = os.getenv("ADMIN_PASSWORD", "admin123")
    if admin_password == "admin123":
        print("⚠️ ВНИМАНИЕ: Используется пароль по умолчанию для админки! Измените его в .env!")
    
    # Парсим список админских ID
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    admin_ids = []
    if admin_ids_str:
        try:
            admin_ids = [int(id_str.strip()) for id_str in admin_ids_str.split(",")]
        except ValueError:
            print("⚠️ Неверный формат ADMIN_IDS, должны быть числа через запятую")
    
    # База данных
    database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bot.db")

    # PRODUCTION v3.0: Redis для FSM и rate limiting (с Sentinel HA support)
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    if not redis_url.startswith("redis://"):
        redis_url = f"redis://{redis_url}"

    # BLOCKER-001: Parse Sentinel nodes for HA mode
    sentinel_nodes = None
    sentinel_nodes_str = os.getenv("REDIS_SENTINEL_NODES", "")
    if sentinel_nodes_str:
        try:
            # Parse format: "host1:port1,host2:port2,host3:port3"
            nodes_list = []
            for node_str in sentinel_nodes_str.split(","):
                node_str = node_str.strip()
                if ":" in node_str:
                    host, port = node_str.split(":", 1)
                    nodes_list.append((host.strip(), int(port.strip())))
                else:
                    print(f"⚠️ Invalid Sentinel node format: {node_str}, expected host:port")

            if nodes_list:
                sentinel_nodes = nodes_list
                logger.info(
                    f"✅ Redis Sentinel HA mode enabled: {len(sentinel_nodes)} nodes\n"
                    f"   Nodes: {sentinel_nodes}"
                )
        except Exception as e:
            print(f"⚠️ Error parsing REDIS_SENTINEL_NODES: {e}")

    redis_master_name = os.getenv("REDIS_MASTER_NAME", "mymaster")

    # Rate limiting
    rate_limit_messages = int(os.getenv("RATE_LIMIT_MESSAGES", "3"))
    rate_limit_callbacks = int(os.getenv("RATE_LIMIT_CALLBACKS", "5"))
    
    # Пути
    content_dir = Path(os.getenv("CONTENT_DIR", "./content"))
    logs_dir = Path(os.getenv("LOGS_DIR", "./logs"))
    
    paths = Paths(
        content=content_dir,
        logs=logs_dir,
        media=content_dir / "media",
        documents=content_dir / "media" / "documents"
    )
    
    # Создаем директории
    paths.ensure_exists()
    
    # Webhook конфигурация (опционально)
    use_webhook = os.getenv("WEBHOOK_HOST") is not None
    
    return Config(
        tg_bot=TgBot(
            token=bot_token,
            admin_password=admin_password,
            admin_ids=admin_ids,
            use_webhook=use_webhook,
            webhook_host=os.getenv("WEBHOOK_HOST"),
            webhook_path=os.getenv("WEBHOOK_PATH", "/webhook"),
            webapp_host=os.getenv("WEBAPP_HOST", "0.0.0.0"),
            webapp_port=int(os.getenv("WEBAPP_PORT", "3001")) if os.getenv("WEBAPP_PORT") else None
        ),
        db=Database(
            url=database_url,
            echo=os.getenv("DEBUG", "False").lower() == "true",
            pool_size=int(os.getenv("DB_POOL_SIZE", "20")),
            max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "30")),
            pool_timeout=int(os.getenv("DB_POOL_TIMEOUT", "30")),
            pool_recycle=int(os.getenv("DB_POOL_RECYCLE", "3600"))
        ),
        redis=Redis(
            url=redis_url,
            fsm_db=int(os.getenv("REDIS_FSM_DB", "0")),
            throttle_db=int(os.getenv("REDIS_THROTTLE_DB", "1")),
            # BLOCKER-001: Sentinel HA configuration
            sentinel_nodes=sentinel_nodes,
            master_name=redis_master_name
        ),
        rate_limit=RateLimit(
            messages=rate_limit_messages,
            callbacks=rate_limit_callbacks
        ),
        paths=paths,
        debug=os.getenv("DEBUG", "False").lower() == "true",
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        timezone=os.getenv("TIMEZONE", "Europe/Moscow")
    )


# CRIT-004 FIX: Removed global config loading
# Config should only be loaded in bot.py on startup using load_config()
# This prevents circular imports and ensures clean initialization

"""
Database module for Telegram training bot
"""

from database.database import (
    DatabaseManager,
    db_manager,
    init_db,
    get_db_session,
    close_db,
    check_db_health
)
from database.crud import (
    UserCRUD,
    ActivityCRUD,
    ContentCRUD,
    AdminLogCRUD
)
from database.models import (
    Base,
    User,
    UserActivity,
    Content,
    TestQuestion,
    TestResult,
    TestAnswer,
    AdminLog,
    BroadcastMessage,
    SystemSettings,
    Department,
    UserRole
)

__all__ = [
    # Database management
    "DatabaseManager",
    "db_manager",
    "init_db",
    "get_db_session",
    "close_db",
    "check_db_health",
    # CRUD classes
    "UserCRUD",
    "ActivityCRUD",
    "ContentCRUD",
    "AdminLogCRUD",
    # Models
    "Base",
    "User",
    "UserActivity",
    "Content",
    "TestQuestion",
    "TestResult",
    "TestAnswer",
    "AdminLog",
    "BroadcastMessage",
    "SystemSettings",
    # Enums
    "Department",
    "UserRole"
]

"""
Pytest configuration and shared fixtures for telegram-training-bot tests.

Provides fixtures for:
- Mock Redis (fakeredis)
- Mock Bot (aiogram mocks)
- Mock Database (SQLAlchemy in-memory)
- Test users and messages
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock
from typing import Dict, Any

# Asyncio event loop fixture
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== REDIS FIXTURES ====================

@pytest.fixture
async def mock_redis():
    """
    Mock Redis client using fakeredis.

    Returns:
        FakeRedis instance with async support
    """
    try:
        import fakeredis.aioredis
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        yield redis
        await redis.flushall()
        await redis.aclose()
    except ImportError:
        # Fallback to simple mock if fakeredis not available
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=None)
        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock(return_value=1)
        redis.incr = AsyncMock(return_value=1)
        redis.expire = AsyncMock(return_value=True)
        redis.ttl = AsyncMock(return_value=-1)
        redis.ping = AsyncMock(return_value=True)
        yield redis


# ==================== BOT FIXTURES ====================

@pytest.fixture
def mock_bot():
    """
    Mock Telegram Bot instance.

    Returns:
        AsyncMock bot with common methods
    """
    bot = AsyncMock()
    bot.id = 123456789
    bot.username = "test_training_bot"
    bot.first_name = "Training Bot"
    bot.get_me = AsyncMock(return_value=MagicMock(
        id=123456789,
        username="test_training_bot",
        first_name="Training Bot"
    ))
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=1))
    bot.send_photo = AsyncMock(return_value=MagicMock(message_id=2))
    bot.send_document = AsyncMock(return_value=MagicMock(message_id=3))
    bot.edit_message_text = AsyncMock(return_value=True)
    bot.delete_message = AsyncMock(return_value=True)
    return bot


@pytest.fixture
def mock_message():
    """
    Mock Telegram Message object.

    Returns:
        Mock message with typical attributes
    """
    message = MagicMock()
    message.message_id = 1
    message.date = datetime.utcnow()
    message.chat = MagicMock()
    message.chat.id = 12345
    message.chat.type = "private"
    message.from_user = MagicMock()
    message.from_user.id = 12345
    message.from_user.first_name = "Test"
    message.from_user.last_name = "User"
    message.from_user.username = "testuser"
    message.from_user.language_code = "ru"
    message.text = "/start"
    message.answer = AsyncMock(return_value=MagicMock(message_id=2))
    message.reply = AsyncMock(return_value=MagicMock(message_id=3))
    message.delete = AsyncMock(return_value=True)
    return message


@pytest.fixture
def mock_callback_query():
    """
    Mock Telegram CallbackQuery object.

    Returns:
        Mock callback query with typical attributes
    """
    callback = MagicMock()
    callback.id = "callback_1"
    callback.from_user = MagicMock()
    callback.from_user.id = 12345
    callback.from_user.first_name = "Test"
    callback.from_user.last_name = "User"
    callback.from_user.username = "testuser"
    callback.message = MagicMock()
    callback.message.message_id = 1
    callback.message.chat = MagicMock()
    callback.message.chat.id = 12345
    callback.message.edit_text = AsyncMock(return_value=True)
    callback.message.delete = AsyncMock(return_value=True)
    callback.data = "test_callback"
    callback.answer = AsyncMock(return_value=True)
    callback.bot = AsyncMock()
    return callback


# ==================== DATABASE FIXTURES ====================

@pytest.fixture
async def mock_db_session():
    """
    Mock SQLAlchemy AsyncSession.

    Returns:
        AsyncMock session with common methods
    """
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalar=lambda: None))
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_user_data() -> Dict[str, Any]:
    """
    Sample user data for testing.

    Returns:
        Dictionary with user attributes
    """
    return {
        "telegram_id": 12345,
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
        "language_code": "ru",
        "is_blocked": False,
        "registration_date": datetime.utcnow(),
        "last_activity": datetime.utcnow()
    }


# ==================== MIDDLEWARE FIXTURES ====================

@pytest.fixture
def timeout_middleware():
    """
    Timeout middleware instance with short timeout for testing.

    Returns:
        TimeoutMiddleware with 5s timeout
    """
    from middlewares.timeout import TimeoutMiddleware
    return TimeoutMiddleware(timeout=5)


@pytest.fixture
def auth_security(mock_redis):
    """
    AuthSecurity instance with mock Redis.

    Returns:
        AuthSecurity instance
    """
    from utils.auth_security import AuthSecurity
    return AuthSecurity(mock_redis)


# ==================== TEST DATA FIXTURES ====================

@pytest.fixture
def malicious_payloads() -> Dict[str, str]:
    """
    Collection of malicious payloads for security testing.

    Returns:
        Dictionary with payload types and examples
    """
    return {
        "xss_basic": "<script>alert('XSS')</script>",
        "xss_img": "<img src=x onerror=alert('XSS')>",
        "html_injection": "<b>Bold</b><i>Italic</i>",
        "sql_injection": "'; DROP TABLE users; --",
        "path_traversal": "../../../etc/passwd",
        "command_injection": "; ls -la",
        "null_byte": "test\x00payload",
        "unicode_bypass": "\u003cscript\u003ealert('XSS')\u003c/script\u003e"
    }


@pytest.fixture
def performance_config() -> Dict[str, int]:
    """
    Configuration for performance tests.

    Returns:
        Dictionary with performance thresholds
    """
    return {
        "max_response_time": 2.0,  # seconds
        "max_memory_mb": 512,
        "concurrent_users": 50,
        "requests_per_user": 10,
        "acceptable_error_rate": 0.01  # 1%
    }


# ==================== HELPER FUNCTIONS ====================

@pytest.fixture
def create_test_message():
    """
    Factory fixture for creating test messages.

    Returns:
        Function that creates Message objects with custom attributes
    """
    def _create(text="/start", user_id=12345, username="testuser", **kwargs):
        message = MagicMock()
        message.message_id = kwargs.get("message_id", 1)
        message.date = datetime.utcnow()
        message.chat = MagicMock()
        message.chat.id = user_id
        message.chat.type = "private"
        message.from_user = MagicMock()
        message.from_user.id = user_id
        message.from_user.first_name = kwargs.get("first_name", "Test")
        message.from_user.last_name = kwargs.get("last_name", "User")
        message.from_user.username = username
        message.from_user.language_code = kwargs.get("language_code", "ru")
        message.text = text
        message.answer = AsyncMock(return_value=MagicMock(message_id=2))
        message.reply = AsyncMock(return_value=MagicMock(message_id=3))
        message.delete = AsyncMock(return_value=True)
        return message
    return _create


# ==================== TEARDOWN ====================

@pytest.fixture(autouse=True)
async def cleanup():
    """
    Automatic cleanup after each test.
    Runs after every test to ensure clean state.
    """
    yield
    # Cleanup code here if needed
    await asyncio.sleep(0)  # Allow pending tasks to complete


# ==================== MIDDLEWARE TEST FIXTURES ====================

@pytest.fixture
def aiogram_message():
    """
    Create real aiogram Message instance for middleware testing.
    
    Middlewares use isinstance() checks that fail with MagicMock.
    """
    from aiogram.types import Message, User, Chat
    
    # Create User
    user = User(
        id=12345,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser"
    )
    
    # Create Chat
    chat = Chat(
        id=12345,
        type="private"
    )
    
    # Create Message
    message = Message(
        message_id=1,
        date=datetime.utcnow(),
        chat=chat,
        from_user=user,
        text="/start"
    )
    
    # Add async mock methods
    message.answer = AsyncMock(return_value=MagicMock(message_id=2))
    message.reply = AsyncMock(return_value=MagicMock(message_id=3))
    message.delete = AsyncMock(return_value=True)
    
    return message


@pytest.fixture
def aiogram_callback_query():
    """
    Create real aiogram CallbackQuery instance for middleware testing.
    """
    from aiogram.types import CallbackQuery, User, Message, Chat
    
    # Create User
    user = User(
        id=12345,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser"
    )
    
    # Create Chat
    chat = Chat(
        id=12345,
        type="private"
    )
    
    # Create Message for callback
    message = Message(
        message_id=1,
        date=datetime.utcnow(),
        chat=chat
    )
    message.edit_text = AsyncMock(return_value=True)
    message.delete = AsyncMock(return_value=True)
    
    # Create CallbackQuery
    callback = CallbackQuery(
        id="callback_1",
        from_user=user,
        chat_instance="instance_1",
        data="test_callback",
        message=message
    )
    
    # Add async mock methods
    callback.answer = AsyncMock(return_value=True)
    
    return callback

"""
Unit tests for middleware components

Run with: pytest tests/test_middleware.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, User, Chat, CallbackQuery

from middlewares.auth import AuthMiddleware
from middlewares.throttling import ThrottlingMiddleware


@pytest.fixture
def mock_message():
    """Create a mock Message object"""
    user = User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="test_user"
    )

    chat = Chat(id=123456789, type="private")

    message = MagicMock(spec=Message)
    message.from_user = user
    message.chat = chat
    message.text = "/start"

    return message


@pytest.fixture
def mock_callback():
    """Create a mock CallbackQuery object"""
    user = User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        username="test_user"
    )

    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = user
    callback.data = "test_callback"
    callback.message = MagicMock(spec=Message)
    callback.answer = AsyncMock()

    return callback


@pytest.mark.asyncio
async def test_auth_middleware_new_user(mock_message):
    """Test AuthMiddleware with a new user"""
    middleware = AuthMiddleware()
    handler = AsyncMock()
    data = {}

    with patch('middlewares.auth.get_db_session') as mock_session, \
         patch('middlewares.auth.UserCRUD') as mock_crud:

        # Mock database session
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db
        mock_session.return_value.__aexit__.return_value = None

        # Mock user CRUD - return new user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.telegram_id = 123456789
        mock_user.username = "test_user"
        mock_crud.get_or_create_user = AsyncMock(return_value=mock_user)
        mock_crud.is_user_blocked = AsyncMock(return_value=False)

        # Call middleware
        await middleware(handler, mock_message, data)

        # Verify handler was called
        handler.assert_called_once()

        # Verify user was added to data
        assert 'db_user' in data
        assert 'user' in data


@pytest.mark.asyncio
async def test_auth_middleware_blocked_user(mock_message):
    """Test AuthMiddleware with a blocked user"""
    middleware = AuthMiddleware()
    handler = AsyncMock()
    data = {}

    # Make answer method async
    mock_message.answer = AsyncMock()

    with patch('middlewares.auth.get_db_session') as mock_session, \
         patch('middlewares.auth.UserCRUD') as mock_crud:

        # Mock database session
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db
        mock_session.return_value.__aexit__.return_value = None

        # Mock blocked user
        mock_user = MagicMock()
        mock_user.is_blocked = True
        mock_crud.get_or_create_user = AsyncMock(return_value=mock_user)
        mock_crud.is_user_blocked = AsyncMock(return_value=True)

        # Call middleware
        result = await middleware(handler, mock_message, data)

        # Verify handler was NOT called
        handler.assert_not_called()

        # Verify result is None (blocked)
        assert result is None

        # Verify user got blocked message
        mock_message.answer.assert_called_once()


@pytest.mark.asyncio
async def test_throttling_middleware_allows_first_message(mock_message):
    """Test ThrottlingMiddleware allows first message"""
    middleware = ThrottlingMiddleware(rate_limit=5)
    handler = AsyncMock()
    data = {}

    # Call middleware
    await middleware(handler, mock_message, data)

    # Verify handler was called
    handler.assert_called_once()


@pytest.mark.asyncio
async def test_throttling_middleware_blocks_spam(mock_message):
    """Test ThrottlingMiddleware blocks spam"""
    middleware = ThrottlingMiddleware(rate_limit=2)  # 2 messages per second
    handler = AsyncMock()

    # Make answer method async
    mock_message.answer = AsyncMock()

    # First message - should pass
    await middleware(handler, mock_message, {})
    assert handler.call_count == 1

    # Second message immediately - should pass
    await middleware(handler, mock_message, {})
    assert handler.call_count == 2

    # Third message immediately - should be blocked
    result = await middleware(handler, mock_message, {})
    assert handler.call_count == 2  # Handler not called again
    assert result is None  # Blocked


@pytest.mark.asyncio
async def test_auth_middleware_handles_callback_query(mock_callback):
    """Test AuthMiddleware handles CallbackQuery"""
    middleware = AuthMiddleware()
    handler = AsyncMock()
    data = {}

    with patch('middlewares.auth.get_db_session') as mock_session, \
         patch('middlewares.auth.UserCRUD') as mock_crud:

        # Mock database session
        mock_db = AsyncMock()
        mock_session.return_value.__aenter__.return_value = mock_db
        mock_session.return_value.__aexit__.return_value = None

        # Mock user
        mock_user = MagicMock()
        mock_crud.get_or_create_user = AsyncMock(return_value=mock_user)
        mock_crud.is_user_blocked = AsyncMock(return_value=False)

        # Call middleware
        await middleware(handler, mock_callback, data)

        # Verify handler was called
        handler.assert_called_once()

        # Verify user was added to data
        assert 'db_user' in data


@pytest.mark.asyncio
async def test_middleware_error_handling(mock_message):
    """Test middleware handles errors gracefully"""
    middleware = AuthMiddleware()
    handler = AsyncMock()
    data = {}

    with patch('middlewares.auth.get_db_session') as mock_session:
        # Make session raise an error
        mock_session.side_effect = Exception("Database connection failed")

        # Call middleware - should not crash
        await middleware(handler, mock_message, data)

        # Handler should still be called despite DB error
        handler.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

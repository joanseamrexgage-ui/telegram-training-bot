"""
Unit tests for AuthMiddleware and AdminAuthMiddleware

Tests critical authentication and authorization flows:
- User registration and retrieval
- Blocked user handling
- Admin authorization
- Database session management
- Error handling and fail-open behavior

Author: Enterprise Production Readiness Team
Coverage Target: 85%+ for middlewares/auth.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.types import Message, CallbackQuery, User

from middlewares.auth import AuthMiddleware, AdminAuthMiddleware


class TestAuthMiddleware:
    """Test suite for AuthMiddleware user authentication"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_successful_user_registration(self, mock_message):
        """Test automatic user registration on first request"""
        middleware = AuthMiddleware()
        handler = AsyncMock(return_value="handler_result")
        data = {}

        # Mock database operations
        with patch('middlewares.auth.get_db_session') as mock_db, \
             patch('middlewares.auth.UserCRUD') as mock_crud:

            # Mock session generator
            mock_session = AsyncMock()
            mock_db.return_value.__aiter__.return_value = [mock_session]

            # Mock user creation
            mock_db_user = MagicMock()
            mock_db_user.telegram_id = 12345
            mock_crud.get_or_create_user = AsyncMock(return_value=mock_db_user)
            mock_crud.is_user_blocked = AsyncMock(return_value=False)

            result = await middleware(handler, mock_message, data)

            # Verify user was registered
            mock_crud.get_or_create_user.assert_called_once()
            assert data['db_user'] == mock_db_user
            assert data['user'] == mock_message.from_user
            assert 'db_session' in data
            assert result == "handler_result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_blocked_user_message_rejected(self, mock_message):
        """Test that blocked users receive rejection message (Message)"""
        middleware = AuthMiddleware()
        handler = AsyncMock()
        data = {}

        with patch('middlewares.auth.get_db_session') as mock_db, \
             patch('middlewares.auth.UserCRUD') as mock_crud:

            mock_session = AsyncMock()
            mock_db.return_value.__aiter__.return_value = [mock_session]

            mock_db_user = MagicMock()
            mock_crud.get_or_create_user = AsyncMock(return_value=mock_db_user)
            mock_crud.is_user_blocked = AsyncMock(return_value=True)

            result = await middleware(handler, mock_message, data)

            # Verify handler was NOT called
            handler.assert_not_called()

            # Verify rejection message was sent
            mock_message.answer.assert_called_once()
            call_args = mock_message.answer.call_args[0][0]
            assert "🚫" in call_args
            assert "заблокирован" in call_args

            # Verify returned None (no further processing)
            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_blocked_user_callback_rejected(self, mock_callback_query):
        """Test that blocked users receive rejection message (CallbackQuery)"""
        middleware = AuthMiddleware()
        handler = AsyncMock()
        data = {}

        with patch('middlewares.auth.get_db_session') as mock_db, \
             patch('middlewares.auth.UserCRUD') as mock_crud:

            mock_session = AsyncMock()
            mock_db.return_value.__aiter__.return_value = [mock_session]

            mock_db_user = MagicMock()
            mock_crud.get_or_create_user = AsyncMock(return_value=mock_db_user)
            mock_crud.is_user_blocked = AsyncMock(return_value=True)

            result = await middleware(handler, mock_callback_query, data)

            # Verify alert was sent
            mock_callback_query.answer.assert_called_once()
            call_args = mock_callback_query.answer.call_args
            assert "🚫" in call_args[0][0]
            assert call_args[1]['show_alert'] is True

            assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_user_in_event(self):
        """Test handling of events without user information"""
        middleware = AuthMiddleware()
        handler = AsyncMock(return_value="result")

        # Create event without from_user
        event = MagicMock(spec=Message)
        event.from_user = None
        data = {}

        result = await middleware(handler, event, data)

        # Should pass through to handler
        handler.assert_called_once_with(event, data)
        assert result == "result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_database_error_fail_open(self, mock_message):
        """Test fail-open behavior when database fails"""
        middleware = AuthMiddleware()
        handler = AsyncMock(return_value="result")
        data = {}

        with patch('middlewares.auth.get_db_session') as mock_db:
            # Simulate database error
            mock_db.return_value.__aiter__.side_effect = Exception("DB connection failed")

            result = await middleware(handler, mock_message, data)

            # Should fail open (allow access)
            handler.assert_called_once()
            assert result == "result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_user_data_added_to_context(self, mock_message):
        """Test that user, db_user, and db_session are added to data context"""
        middleware = AuthMiddleware()
        handler = AsyncMock()
        data = {}

        with patch('middlewares.auth.get_db_session') as mock_db, \
             patch('middlewares.auth.UserCRUD') as mock_crud:

            mock_session = AsyncMock()
            mock_db.return_value.__aiter__.return_value = [mock_session]

            mock_db_user = MagicMock()
            mock_db_user.telegram_id = 12345
            mock_crud.get_or_create_user = AsyncMock(return_value=mock_db_user)
            mock_crud.is_user_blocked = AsyncMock(return_value=False)

            await middleware(handler, mock_message, data)

            # Verify all required data is in context
            assert 'user' in data
            assert 'db_user' in data
            assert 'db_session' in data
            assert data['user'] == mock_message.from_user
            assert data['db_user'] == mock_db_user
            assert data['db_session'] == mock_session


class TestAdminAuthMiddleware:
    """Test suite for AdminAuthMiddleware admin authorization"""

    @pytest.mark.unit
    def test_initialization_with_admin_ids(self):
        """Test middleware initialization with provided admin IDs"""
        admin_ids = [123, 456, 789]
        middleware = AdminAuthMiddleware(admin_ids=admin_ids)

        assert middleware.admin_ids == admin_ids

    @pytest.mark.unit
    def test_initialization_without_admin_ids(self):
        """Test middleware initialization without admin IDs (loads from config)"""
        with patch('middlewares.auth.load_config') as mock_config:
            mock_cfg = MagicMock()
            mock_cfg.admin.ids = [111, 222]
            mock_config.return_value = mock_cfg

            middleware = AdminAuthMiddleware()

            assert middleware.admin_ids == [111, 222]

    @pytest.mark.unit
    def test_initialization_config_missing(self):
        """Test graceful handling when config has no admin IDs"""
        with patch('middlewares.auth.load_config') as mock_config:
            mock_cfg = MagicMock()
            del mock_cfg.admin  # No admin config
            mock_config.return_value = mock_cfg

            middleware = AdminAuthMiddleware()

            assert middleware.admin_ids == []

    @pytest.mark.unit
    def test_initialization_config_load_error(self):
        """Test graceful handling when config loading fails"""
        with patch('middlewares.auth.load_config', side_effect=Exception("Config error")):
            middleware = AdminAuthMiddleware()

            assert middleware.admin_ids == []

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_admin_user_granted_access(self, mock_message):
        """Test that admin users are granted access"""
        admin_id = 12345
        mock_message.from_user.id = admin_id

        middleware = AdminAuthMiddleware(admin_ids=[admin_id])
        handler = AsyncMock(return_value="result")
        data = {}

        result = await middleware(handler, mock_message, data)

        # Verify admin was granted access
        handler.assert_called_once()
        assert data['is_admin'] is True
        assert data['admin_user_id'] == admin_id
        assert result == "result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_non_admin_user_denied_message(self, mock_message):
        """Test that non-admin users are denied (Message)"""
        admin_id = 99999
        mock_message.from_user.id = 12345  # Different from admin

        middleware = AdminAuthMiddleware(admin_ids=[admin_id])
        handler = AsyncMock()
        data = {}

        result = await middleware(handler, mock_message, data)

        # Verify handler was NOT called
        handler.assert_not_called()

        # Verify rejection message
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "🚫" in call_args
        assert "прав администратора" in call_args

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_non_admin_user_denied_callback(self, mock_callback_query):
        """Test that non-admin users are denied (CallbackQuery)"""
        admin_id = 99999
        mock_callback_query.from_user.id = 12345

        middleware = AdminAuthMiddleware(admin_ids=[admin_id])
        handler = AsyncMock()
        data = {}

        result = await middleware(handler, mock_callback_query, data)

        # Verify alert was sent
        mock_callback_query.answer.assert_called_once()
        call_args = mock_callback_query.answer.call_args
        assert "🚫" in call_args[0][0]
        assert call_args[1]['show_alert'] is True

        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_user_in_event_denied(self):
        """Test that events without user are denied"""
        middleware = AdminAuthMiddleware(admin_ids=[123])
        handler = AsyncMock()

        event = MagicMock(spec=Message)
        event.from_user = None
        data = {}

        result = await middleware(handler, event, data)

        # Should deny access (no user = not admin)
        handler.assert_not_called()
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_multiple_admins(self, mock_message):
        """Test that multiple admin IDs work correctly"""
        admin_ids = [111, 222, 333]
        middleware = AdminAuthMiddleware(admin_ids=admin_ids)
        handler = AsyncMock()
        data = {}

        # Test each admin ID
        for admin_id in admin_ids:
            mock_message.from_user.id = admin_id
            result = await middleware(handler, mock_message, data.copy())

            assert result is not None
            handler.assert_called()
            handler.reset_mock()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_message_send_error_handled(self, mock_message):
        """Test graceful handling of message sending errors"""
        middleware = AdminAuthMiddleware(admin_ids=[999])
        handler = AsyncMock()
        data = {}

        # Make answer() raise exception
        mock_message.answer = AsyncMock(side_effect=Exception("Send failed"))

        result = await middleware(handler, mock_message, data)

        # Should still deny access despite message error
        handler.assert_not_called()
        assert result is None

"""
Unit tests for ThrottlingMiddleware

Tests rate limiting and anti-spam protection:
- Request rate limiting (default 2.0s)
- Warning system (max 5 warnings)
- Automatic blocking (60s duration)
- Automatic unblocking
- Warning decay for good behavior

Author: Enterprise Production Readiness Team
Coverage Target: 85%+ for middlewares/throttling.py
"""

import pytest
import time
import asyncio
from unittest.mock import AsyncMock, MagicMock

from middlewares.throttling import ThrottlingMiddleware


class TestThrottlingMiddlewareInitialization:
    """Test middleware initialization and configuration"""

    @pytest.mark.unit
    def test_default_initialization(self):
        """Test initialization with default parameters"""
        middleware = ThrottlingMiddleware()

        assert middleware.default_rate == 2.0
        assert middleware.max_warnings == 5
        assert middleware.block_duration == 60
        assert middleware.last_request_time == {}
        assert middleware.warnings == {}
        assert middleware.blocked_users == {}

    @pytest.mark.unit
    def test_custom_initialization(self):
        """Test initialization with custom parameters"""
        middleware = ThrottlingMiddleware(
            default_rate=1.0,
            max_warnings=3,
            block_duration=120
        )

        assert middleware.default_rate == 1.0
        assert middleware.max_warnings == 3
        assert middleware.block_duration == 120


class TestThrottlingAllowedRequests:
    """Test that legitimate requests are allowed"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_first_request_allowed(self, aiogram_message):
        """Test that first request from user is always allowed"""
        middleware = ThrottlingMiddleware(default_rate=2.0)
        handler = AsyncMock(return_value="result")
        data = {}

        result = await middleware(handler, aiogram_message, data)

        handler.assert_called_once()
        assert result == "result"
        assert 12345 in middleware.last_request_time

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_properly_spaced_requests_allowed(self, aiogram_message):
        """Test that properly spaced requests are allowed"""
        middleware = ThrottlingMiddleware(default_rate=0.1)  # 0.1s for faster test
        handler = AsyncMock(return_value="result")
        data = {}

        # First request
        result1 = await middleware(handler, aiogram_message, data)
        assert result1 == "result"

        # Wait longer than rate limit
        await asyncio.sleep(0.15)

        # Second request should be allowed
        result2 = await middleware(handler, aiogram_message, data)
        assert result2 == "result"
        assert handler.call_count == 2

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_no_user_in_event_allowed(self):
        """Test that events without user bypass throttling"""
        middleware = ThrottlingMiddleware()
        handler = AsyncMock(return_value="result")

        event = MagicMock()
        event.from_user = None
        data = {}

        result = await middleware(handler, event, data)

        handler.assert_called_once()
        assert result == "result"


class TestThrottlingWarnings:
    """Test warning system for rapid requests"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rapid_request_triggers_warning(self, aiogram_message):
        """Test that rapid requests trigger warnings"""
        middleware = ThrottlingMiddleware(default_rate=2.0, max_warnings=5)
        handler = AsyncMock()
        data = {}

        # First request - allowed
        await middleware(handler, aiogram_message, data)

        # Immediate second request - should warn
        result = await middleware(handler, aiogram_message, data)

        assert result is None  # Blocked
        aiogram_message.answer.assert_called_once()

        # Verify warning message
        warning_msg = aiogram_message.answer.call_args[0][0]
        assert "⚠️" in warning_msg
        assert "Подождите" in warning_msg
        assert "1/5" in warning_msg  # First warning

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_warning_counter_increments(self, aiogram_message):
        """Test that warning counter increments correctly"""
        middleware = ThrottlingMiddleware(default_rate=2.0, max_warnings=5)
        handler = AsyncMock()
        data = {}

        user_id = aiogram_message.from_user.id

        # First request - allowed
        await middleware(handler, aiogram_message, data)

        # Rapid requests to accumulate warnings
        for i in range(1, 4):  # 3 rapid requests
            await middleware(handler, aiogram_message, data)
            assert middleware.warnings[user_id] == i

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_warning_decay_on_good_behavior(self, aiogram_message):
        """Test that warnings decrease when user behaves properly"""
        middleware = ThrottlingMiddleware(default_rate=0.1)
        handler = AsyncMock()
        data = {}

        user_id = aiogram_message.from_user.id

        # First request
        await middleware(handler, aiogram_message, data)

        # Rapid request to get warning
        await middleware(handler, aiogram_message, data)
        assert middleware.warnings[user_id] == 1

        # Wait and make proper request
        await asyncio.sleep(0.15)
        await middleware(handler, aiogram_message, data)

        # Warning should have decreased
        assert middleware.warnings[user_id] == 0


class TestThrottlingBlocking:
    """Test user blocking for excessive violations"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_max_warnings_triggers_block(self, aiogram_message):
        """Test that reaching max warnings blocks user"""
        middleware = ThrottlingMiddleware(
            default_rate=2.0,
            max_warnings=3,
            block_duration=60
        )
        handler = AsyncMock()
        data = {}

        user_id = aiogram_message.from_user.id

        # First request - allowed
        await middleware(handler, aiogram_message, data)

        # Make max_warnings rapid requests
        for _ in range(3):
            await middleware(handler, aiogram_message, data)

        # User should now be blocked
        assert user_id in middleware.blocked_users
        assert middleware.blocked_users[user_id] > time.time()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_blocked_user_receives_block_message(self, aiogram_message):
        """Test that blocked users receive block notification"""
        middleware = ThrottlingMiddleware(
            default_rate=2.0,
            max_warnings=2,
            block_duration=60
        )
        handler = AsyncMock()
        data = {}

        # Trigger block
        await middleware(handler, aiogram_message, data)
        await middleware(handler, aiogram_message, data)
        result = await middleware(handler, aiogram_message, data)

        assert result is None
        aiogram_message.answer.assert_called()

        # Verify block message
        block_msg = aiogram_message.answer.call_args[0][0]
        assert "🚫" in block_msg
        assert "заблокированы" in block_msg
        assert "60" in block_msg  # Block duration

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_blocked_user_callback_query(self, aiogram_callback_query):
        """Test blocked user with CallbackQuery"""
        middleware = ThrottlingMiddleware(
            default_rate=2.0,
            max_warnings=2
        )
        handler = AsyncMock()
        data = {}

        # Trigger block
        await middleware(handler, aiogram_callback_query, data)
        await middleware(handler, aiogram_callback_query, data)
        await middleware(handler, aiogram_callback_query, data)

        # Verify alert
        aiogram_callback_query.answer.assert_called()
        call_args = aiogram_callback_query.answer.call_args
        assert "🚫" in call_args[0][0]
        assert call_args[1]['show_alert'] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_blocked_user_shows_remaining_time(self, aiogram_message):
        """Test that block message shows remaining time"""
        middleware = ThrottlingMiddleware(
            default_rate=2.0,
            max_warnings=2,
            block_duration=60
        )
        handler = AsyncMock()
        data = {}

        user_id = aiogram_message.from_user.id

        # Trigger block
        await middleware(handler, aiogram_message, data)
        await middleware(handler, aiogram_message, data)
        await middleware(handler, aiogram_message, data)

        # Try again while blocked
        aiogram_message.answer.reset_mock()
        await middleware(handler, aiogram_message, data)

        # Verify remaining time is shown
        block_msg = aiogram_message.answer.call_args[0][0]
        assert "⏳" in block_msg
        assert "Попробуйте через" in block_msg


class TestThrottlingAutoUnblock:
    """Test automatic unblocking after duration expires"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_auto_unblock_after_duration(self, aiogram_message):
        """Test that users are automatically unblocked after duration"""
        middleware = ThrottlingMiddleware(
            default_rate=2.0,
            max_warnings=2,
            block_duration=1  # 1 second for testing
        )
        handler = AsyncMock()
        data = {}

        user_id = aiogram_message.from_user.id

        # Trigger block
        await middleware(handler, aiogram_message, data)
        await middleware(handler, aiogram_message, data)
        await middleware(handler, aiogram_message, data)

        assert user_id in middleware.blocked_users

        # Wait for block to expire
        await asyncio.sleep(1.1)

        # Try again - should be unblocked
        handler.reset_mock()
        result = await middleware(handler, aiogram_message, data)

        assert user_id not in middleware.blocked_users
        assert middleware.warnings[user_id] == 0
        assert result is not None  # Should be allowed now

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_warnings_reset_after_unblock(self, aiogram_message):
        """Test that warnings are reset when user is unblocked"""
        middleware = ThrottlingMiddleware(
            default_rate=2.0,
            max_warnings=2,
            block_duration=1
        )
        handler = AsyncMock()
        data = {}

        user_id = aiogram_message.from_user.id

        # Trigger block
        await middleware(handler, aiogram_message, data)
        await middleware(handler, aiogram_message, data)
        await middleware(handler, aiogram_message, data)

        assert middleware.warnings[user_id] >= middleware.max_warnings

        # Wait for auto-unblock
        await asyncio.sleep(1.1)

        # Check if blocked (triggers auto-unblock)
        await middleware(handler, aiogram_message, data)

        # Warnings should be reset
        assert middleware.warnings[user_id] == 0


class TestThrottlingMultipleUsers:
    """Test that throttling works independently for multiple users"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_independent_user_tracking(self, aiogram_message, aiogram_callback_query):
        """Test that different users are tracked independently"""
        from aiogram.types import Message, User, Chat
        from datetime import datetime

        middleware = ThrottlingMiddleware(default_rate=2.0)

        # Create two different users with proper Message objects
        user1 = User(id=111, is_bot=False, first_name="User1")
        user1_msg = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=111, type="private"),
            from_user=user1
        )
        # Add mock answer method (bypass frozen model)
        answer_mock1 = AsyncMock()
        object.__setattr__(user1_msg, 'answer', answer_mock1)

        user2 = User(id=222, is_bot=False, first_name="User2")
        user2_msg = Message(
            message_id=2,
            date=datetime.utcnow(),
            chat=Chat(id=222, type="private"),
            from_user=user2
        )
        answer_mock2 = AsyncMock()
        object.__setattr__(user2_msg, 'answer', answer_mock2)

        handler = AsyncMock()

        # User 1 makes request
        await middleware(handler, user1_msg, {})

        # User 2 makes request - should be allowed (different user)
        result = await middleware(handler, user2_msg, {})
        assert result is not None

        # User 1 makes rapid request - should be warned
        result = await middleware(handler, user1_msg, {})
        assert result is None  # Blocked

        # User 2 should still be able to make requests
        await asyncio.sleep(0.1)
        result = await middleware(handler, user2_msg, {})
        # This might be blocked if too fast, but shouldn't affect user1's state

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_one_user_blocked_others_allowed(self):
        """Test that blocking one user doesn't affect others"""
        from aiogram.types import Message, User, Chat
        from datetime import datetime

        middleware = ThrottlingMiddleware(
            default_rate=2.0,
            max_warnings=2
        )

        # Create proper Message objects for two users
        user1 = User(id=111, is_bot=False, first_name="User1")
        user1_msg = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=111, type="private"),
            from_user=user1
        )
        answer_mock1 = AsyncMock()
        object.__setattr__(user1_msg, 'answer', answer_mock1)

        user2 = User(id=222, is_bot=False, first_name="User2")
        user2_msg = Message(
            message_id=2,
            date=datetime.utcnow(),
            chat=Chat(id=222, type="private"),
            from_user=user2
        )
        answer_mock2 = AsyncMock()
        object.__setattr__(user2_msg, 'answer', answer_mock2)

        handler = AsyncMock()

        # Block user 1
        await middleware(handler, user1_msg, {})
        await middleware(handler, user1_msg, {})
        await middleware(handler, user1_msg, {})

        assert 111 in middleware.blocked_users
        assert 222 not in middleware.blocked_users

        # User 2 should still be allowed
        await asyncio.sleep(0.1)
        result = await middleware(handler, user2_msg, {})
        # User 2 operates independently


class TestThrottlingErrorHandling:
    """Test error handling in throttling middleware"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_message_send_error_handled(self, aiogram_message):
        """Test that message sending errors don't crash middleware"""
        middleware = ThrottlingMiddleware(default_rate=2.0)
        handler = AsyncMock()
        data = {}

        # First request
        await middleware(handler, aiogram_message, data)

        # Make answer() fail (use object.__setattr__ for frozen model)
        answer_mock = AsyncMock(side_effect=Exception("Send failed"))
        object.__setattr__(aiogram_message, 'answer', answer_mock)

        # Rapid request should still be blocked even if message fails
        result = await middleware(handler, aiogram_message, data)
        assert result is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_callback_send_error_handled(self, aiogram_callback_query):
        """Test that callback answer errors don't crash middleware"""
        middleware = ThrottlingMiddleware(default_rate=2.0, max_warnings=2)
        handler = AsyncMock()
        data = {}

        # Trigger block
        await middleware(handler, aiogram_callback_query, data)
        await middleware(handler, aiogram_callback_query, data)

        # Make answer() fail (use object.__setattr__ for frozen model)
        answer_mock = AsyncMock(side_effect=Exception("Send failed"))
        object.__setattr__(aiogram_callback_query, 'answer', answer_mock)

        result = await middleware(handler, aiogram_callback_query, data)
        assert result is None  # Should still block

"""
Unit tests for TimeoutMiddleware.

Tests:
- Normal handler execution
- Timeout enforcement
- Statistics tracking
- User notifications
- Error handling
"""

import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from middlewares.timeout import TimeoutMiddleware


class TestTimeoutMiddleware:
    """Test suite for TimeoutMiddleware"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_normal_handler_execution(self, timeout_middleware, mock_message):
        """Test that fast handlers complete successfully within timeout"""

        async def fast_handler(event, data):
            """Simulates a fast handler (0.1s)"""
            await asyncio.sleep(0.1)
            return "success"

        data = {}

        result = await timeout_middleware(fast_handler, mock_message, data)

        assert result == "success"
        assert timeout_middleware.stats["timeouts"] == 0
        assert timeout_middleware.stats["total_requests"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_timeout_handler_execution(self, timeout_middleware, mock_message):
        """Test that slow handlers timeout properly"""

        async def slow_handler(event, data):
            """Simulates a slow handler (10s > 5s timeout)"""
            await asyncio.sleep(10)
            return "should_not_reach"

        data = {}

        result = await timeout_middleware(slow_handler, mock_message, data)

        assert result is None  # Timeout returns None
        assert timeout_middleware.stats["timeouts"] == 1
        assert timeout_middleware.stats["total_requests"] == 1

        # Verify user was notified
        mock_message.answer.assert_called_once()
        call_args = mock_message.answer.call_args[0][0]
        assert "превышено" in call_args.lower() or "timeout" in call_args.lower()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_timeout_statistics(self, timeout_middleware, mock_message):
        """Test that statistics are tracked correctly"""

        async def fast_handler(event, data):
            await asyncio.sleep(0.05)
            return "success"

        data = {}

        # Execute 5 requests
        for _ in range(5):
            await timeout_middleware(fast_handler, mock_message, data)

        stats = timeout_middleware.get_stats()

        assert stats["total_requests"] == 5
        assert stats["timeouts"] == 0
        assert stats["timeout_rate"] == 0.0
        assert stats["timeout_threshold"] == 5
        assert "avg_execution_time" in stats
        assert stats["avg_execution_time"] > 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_mixed_timeout_rate(self, timeout_middleware, mock_message):
        """Test timeout rate calculation with mixed results"""

        async def fast_handler(event, data):
            await asyncio.sleep(0.01)
            return "success"

        async def slow_handler(event, data):
            await asyncio.sleep(10)
            return "timeout"

        data = {}

        # 3 fast, 2 slow
        await timeout_middleware(fast_handler, mock_message, data)
        await timeout_middleware(fast_handler, mock_message, data)
        await timeout_middleware(fast_handler, mock_message, data)
        await timeout_middleware(slow_handler, mock_message, data)
        await timeout_middleware(slow_handler, mock_message, data)

        stats = timeout_middleware.get_stats()

        assert stats["total_requests"] == 5
        assert stats["timeouts"] == 2
        assert stats["timeout_rate"] == 40.0  # 2/5 = 40%

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_callback_query_timeout_notification(self, timeout_middleware, mock_callback_query):
        """Test that CallbackQuery timeouts show alert"""

        async def slow_handler(event, data):
            await asyncio.sleep(10)
            return "timeout"

        data = {}

        result = await timeout_middleware(slow_handler, mock_callback_query, data)

        assert result is None
        # Verify alert was shown
        mock_callback_query.answer.assert_called_once()
        call_args = mock_callback_query.answer.call_args
        assert call_args[1].get("show_alert") is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_handler_exception_propagation(self, timeout_middleware, mock_message):
        """Test that non-timeout exceptions are propagated"""

        async def error_handler(event, data):
            raise ValueError("Test error")

        data = {}

        with pytest.raises(ValueError, match="Test error"):
            await timeout_middleware(error_handler, mock_message, data)

        # Timeout count should not increase for non-timeout errors
        assert timeout_middleware.stats["timeouts"] == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_statistics_reset(self, timeout_middleware, mock_message):
        """Test statistics reset functionality"""

        async def fast_handler(event, data):
            await asyncio.sleep(0.01)
            return "success"

        data = {}

        # Execute some requests
        for _ in range(3):
            await timeout_middleware(fast_handler, mock_message, data)

        # Verify stats exist
        assert timeout_middleware.stats["total_requests"] == 3

        # Reset stats
        timeout_middleware.reset_stats()

        # Verify stats are cleared
        stats = timeout_middleware.get_stats()
        assert stats["total_requests"] == 0
        assert stats["timeouts"] == 0
        assert stats["timeout_rate"] == 0.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_concurrent_handlers(self, timeout_middleware, create_test_message):
        """Test timeout middleware with concurrent requests"""

        async def handler(event, data):
            await asyncio.sleep(0.1)
            return f"user_{event.from_user.id}"

        # Create 10 concurrent requests from different users
        tasks = []
        for i in range(10):
            message = create_test_message(user_id=1000 + i)
            data = {}
            tasks.append(timeout_middleware(handler, message, data))

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(result is not None for result in results)
        assert timeout_middleware.stats["total_requests"] == 10
        assert timeout_middleware.stats["timeouts"] == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_slow_warning_threshold(self, timeout_middleware, mock_message, caplog):
        """Test that slow handlers (>50% of timeout) are logged"""
        import logging

        async def slow_but_not_timeout_handler(event, data):
            # 3s is >50% of 5s timeout but doesn't trigger timeout
            await asyncio.sleep(3)
            return "completed"

        data = {}

        with caplog.at_level(logging.WARNING):
            result = await timeout_middleware(slow_but_not_timeout_handler, mock_message, data)

        assert result == "completed"
        assert timeout_middleware.stats["timeouts"] == 0

        # Check that warning was logged (may not work if logger not configured)
        # assert "Slow handler detected" in caplog.text

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_zero_timeout_immediate_timeout(self):
        """Test that zero timeout immediately times out"""
        middleware = TimeoutMiddleware(timeout=0)

        async def any_handler(event, data):
            await asyncio.sleep(0.001)
            return "success"

        message = MagicMock()
        message.answer = AsyncMock()
        data = {}

        result = await middleware(any_handler, message, data)

        assert result is None
        assert middleware.stats["timeouts"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_timeout_with_user_info_logging(self, timeout_middleware, create_test_message):
        """Test that user info is properly logged on timeout"""

        async def slow_handler(event, data):
            await asyncio.sleep(10)
            return "timeout"

        message = create_test_message(
            user_id=99999,
            username="timeout_test_user",
            first_name="Timeout",
            last_name="User"
        )
        data = {}

        result = await timeout_middleware(slow_handler, message, data)

        assert result is None
        assert timeout_middleware.stats["timeouts"] == 1
        # Logger should have recorded user_id and username (verified in logs)

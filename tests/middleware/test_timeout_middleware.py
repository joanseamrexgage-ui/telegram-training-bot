"""
Unit tests for TimeoutMiddleware

Tests DoS protection and handler timeout enforcement:
- 30-second timeout enforcement
- Slow handler detection (>50% threshold)
- Statistics tracking
- User-friendly timeout messages
- Performance monitoring

Author: Enterprise Production Readiness Team
Coverage Target: 85%+ for middlewares/timeout.py
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from middlewares.timeout import TimeoutMiddleware


class TestTimeoutMiddlewareInitialization:
    """Test middleware initialization and configuration"""

    @pytest.mark.unit
    def test_default_initialization(self):
        """Test initialization with default 30s timeout"""
        middleware = TimeoutMiddleware()

        assert middleware.timeout == 30
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["total_requests"] == 0
        assert middleware.stats["total_execution_time"] == 0.0

    @pytest.mark.unit
    def test_custom_timeout(self):
        """Test initialization with custom timeout"""
        middleware = TimeoutMiddleware(timeout=60)

        assert middleware.timeout == 60

    @pytest.mark.unit
    def test_initial_stats(self):
        """Test that statistics are properly initialized"""
        middleware = TimeoutMiddleware()
        stats = middleware.get_stats()

        assert stats["total_requests"] == 0
        assert stats["timeouts"] == 0
        assert stats["timeout_rate"] == 0.0
        assert stats["timeout_threshold"] == 30
        assert stats["avg_execution_time"] == 0.0


class TestTimeoutNormalExecution:
    """Test normal handler execution within timeout"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_fast_handler_allowed(self, mock_message):
        """Test that fast handlers execute normally"""
        middleware = TimeoutMiddleware(timeout=5)

        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "result"

        result = await middleware(fast_handler, mock_message, {})

        assert result == "result"
        assert middleware.stats["total_requests"] == 1
        assert middleware.stats["timeouts"] == 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_statistics_tracking(self, mock_message):
        """Test that execution statistics are tracked"""
        middleware = TimeoutMiddleware(timeout=5)

        async def handler(event, data):
            await asyncio.sleep(0.1)
            return "ok"

        # Execute multiple requests
        for _ in range(3):
            await middleware(handler, mock_message, {})

        stats = middleware.get_stats()
        assert stats["total_requests"] == 3
        assert stats["timeouts"] == 0
        assert stats["avg_execution_time"] > 0.0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_execution_time_tracking(self, mock_message):
        """Test that execution time is properly tracked"""
        middleware = TimeoutMiddleware(timeout=5)

        async def handler(event, data):
            await asyncio.sleep(0.2)
            return "ok"

        await middleware(handler, mock_message, {})

        assert middleware.stats["total_execution_time"] >= 0.2
        stats = middleware.get_stats()
        assert stats["avg_execution_time"] >= 0.2


class TestTimeoutDetection:
    """Test timeout detection and handling"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_slow_handler_times_out(self, mock_message):
        """Test that slow handlers trigger timeout"""
        middleware = TimeoutMiddleware(timeout=1)

        async def slow_handler(event, data):
            await asyncio.sleep(2)  # Exceed timeout
            return "should_not_return"

        result = await middleware(slow_handler, mock_message, {})

        assert result is None  # Timeout returns None
        assert middleware.stats["timeouts"] == 1
        assert middleware.stats["total_requests"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_timeout_message_sent_to_user(self, mock_message):
        """Test that user receives timeout notification (Message)"""
        middleware = TimeoutMiddleware(timeout=1)

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        await middleware(slow_handler, mock_message, {})

        # Verify timeout message was sent
        mock_message.answer.assert_called_once()
        timeout_msg = mock_message.answer.call_args[0][0]
        assert "⚠️" in timeout_msg
        assert "Время обработки превышено" in timeout_msg

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_timeout_callback_alert(self, mock_callback_query):
        """Test that callback query receives timeout alert"""
        middleware = TimeoutMiddleware(timeout=1)

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        await middleware(slow_handler, mock_callback_query, {})

        # Verify alert was sent
        mock_callback_query.answer.assert_called_once()
        call_args = mock_callback_query.answer.call_args
        assert "Timeout" in call_args[0][0]
        assert call_args[1]['show_alert'] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_multiple_timeouts_tracked(self, mock_message):
        """Test that multiple timeouts are properly counted"""
        middleware = TimeoutMiddleware(timeout=1)

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        # Execute multiple slow requests
        for _ in range(3):
            await middleware(slow_handler, mock_message, {})

        assert middleware.stats["timeouts"] == 3
        assert middleware.stats["total_requests"] == 3

        stats = middleware.get_stats()
        assert stats["timeout_rate"] == 100.0  # 100% timeout rate


class TestSlowHandlerWarning:
    """Test detection and logging of slow handlers"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_slow_handler_logged(self, mock_message):
        """Test that handlers exceeding 50% threshold are logged"""
        middleware = TimeoutMiddleware(timeout=2)

        async def slow_handler(event, data):
            await asyncio.sleep(1.2)  # 60% of timeout
            return "result"

        with patch('middlewares.timeout.logger') as mock_logger:
            result = await middleware(slow_handler, mock_message, {})

            # Handler should complete but be logged as slow
            assert result == "result"
            mock_logger.warning.assert_called()

            warning_msg = mock_logger.warning.call_args[0][0]
            assert "Slow handler detected" in warning_msg

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_fast_handler_not_logged(self, mock_message):
        """Test that fast handlers (<50% threshold) are not logged as slow"""
        middleware = TimeoutMiddleware(timeout=2)

        async def fast_handler(event, data):
            await asyncio.sleep(0.5)  # 25% of timeout
            return "result"

        with patch('middlewares.timeout.logger') as mock_logger:
            await middleware(fast_handler, mock_message, {})

            # Should NOT log warning for fast handler
            warning_calls = [
                call for call in mock_logger.warning.call_args_list
                if "Slow handler detected" in str(call)
            ]
            assert len(warning_calls) == 0


class TestTimeoutStatistics:
    """Test statistics collection and reporting"""

    @pytest.mark.unit
    def test_timeout_rate_calculation(self):
        """Test timeout rate percentage calculation"""
        middleware = TimeoutMiddleware()

        # No requests yet
        assert middleware._get_timeout_rate() == 0.0

        # Simulate some requests
        middleware.stats["total_requests"] = 10
        middleware.stats["timeouts"] = 2

        assert middleware._get_timeout_rate() == 20.0

    @pytest.mark.unit
    def test_get_stats_structure(self):
        """Test that get_stats returns correct structure"""
        middleware = TimeoutMiddleware(timeout=30)
        middleware.stats["total_requests"] = 100
        middleware.stats["timeouts"] = 5
        middleware.stats["total_execution_time"] = 50.0

        stats = middleware.get_stats()

        assert "total_requests" in stats
        assert "timeouts" in stats
        assert "timeout_rate" in stats
        assert "timeout_threshold" in stats
        assert "avg_execution_time" in stats

        assert stats["total_requests"] == 100
        assert stats["timeouts"] == 5
        assert stats["timeout_rate"] == 5.0
        assert stats["timeout_threshold"] == 30
        assert stats["avg_execution_time"] == 0.5

    @pytest.mark.unit
    def test_reset_stats(self):
        """Test that reset_stats clears all counters"""
        middleware = TimeoutMiddleware()

        # Populate stats
        middleware.stats["total_requests"] = 50
        middleware.stats["timeouts"] = 10
        middleware.stats["total_execution_time"] = 100.0

        # Reset
        middleware.reset_stats()

        # Verify reset
        assert middleware.stats["total_requests"] == 0
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["total_execution_time"] == 0.0


class TestErrorHandling:
    """Test error handling in middleware"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_handler_exception_propagated(self, mock_message):
        """Test that handler exceptions are propagated (not swallowed)"""
        middleware = TimeoutMiddleware(timeout=5)

        async def failing_handler(event, data):
            raise ValueError("Handler error")

        with pytest.raises(ValueError, match="Handler error"):
            await middleware(failing_handler, mock_message, {})

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_exception_logged_with_details(self, mock_message):
        """Test that exceptions are logged with handler details"""
        middleware = TimeoutMiddleware(timeout=5)

        async def failing_handler(event, data):
            raise RuntimeError("Test error")

        with patch('middlewares.timeout.logger') as mock_logger:
            with pytest.raises(RuntimeError):
                await middleware(failing_handler, mock_message, {})

            # Verify error was logged
            mock_logger.error.assert_called()
            error_msg = mock_logger.error.call_args[0][0]
            assert "Error in TimeoutMiddleware" in error_msg

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_message_send_error_handled(self, mock_message):
        """Test that errors sending timeout message don't crash middleware"""
        middleware = TimeoutMiddleware(timeout=1)

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        # Make answer() fail
        mock_message.answer = AsyncMock(side_effect=Exception("Send failed"))

        # Should not raise exception
        result = await middleware(slow_handler, mock_message, {})
        assert result is None  # Timeout still processed


class TestUserInformationExtraction:
    """Test user information extraction for logging"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_user_info_extracted_from_message(self):
        """Test user info is extracted from Message"""
        middleware = TimeoutMiddleware(timeout=1)

        message = MagicMock()
        message.from_user = MagicMock()
        message.from_user.id = 12345
        message.from_user.username = "testuser"
        message.answer = AsyncMock()

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        with patch('middlewares.timeout.logger') as mock_logger:
            await middleware(slow_handler, message, {})

            # Verify user info in log
            error_call = mock_logger.error.call_args[0][0]
            assert "12345" in error_call
            assert "@testuser" in error_call

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_user_info_extracted_from_callback(self):
        """Test user info is extracted from CallbackQuery"""
        middleware = TimeoutMiddleware(timeout=1)

        callback = MagicMock()
        callback.from_user = MagicMock()
        callback.from_user.id = 54321
        callback.from_user.username = "callbackuser"
        callback.answer = AsyncMock()

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        with patch('middlewares.timeout.logger') as mock_logger:
            await middleware(slow_handler, callback, {})

            error_call = mock_logger.error.call_args[0][0]
            assert "54321" in error_call

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_missing_user_info_handled(self):
        """Test that missing user info doesn't crash logging"""
        middleware = TimeoutMiddleware(timeout=1)

        event = MagicMock()
        # No from_user attribute

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        # Should not raise exception
        result = await middleware(slow_handler, event, {})
        assert result is None


class TestPerformanceMonitoring:
    """Test performance monitoring capabilities"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_average_execution_time_calculation(self, mock_message):
        """Test average execution time is calculated correctly"""
        middleware = TimeoutMiddleware(timeout=5)

        async def handler1(event, data):
            await asyncio.sleep(0.1)
            return "ok"

        async def handler2(event, data):
            await asyncio.sleep(0.3)
            return "ok"

        await middleware(handler1, mock_message, {})
        await middleware(handler2, mock_message, {})

        stats = middleware.get_stats()
        # Average should be around 0.2 (0.1 + 0.3) / 2
        assert 0.15 <= stats["avg_execution_time"] <= 0.35

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_stats_after_mixed_results(self, mock_message):
        """Test statistics after mix of successful and timed out requests"""
        middleware = TimeoutMiddleware(timeout=1)

        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "ok"

        async def slow_handler(event, data):
            await asyncio.sleep(2)

        # Mix of fast and slow
        await middleware(fast_handler, mock_message, {})
        await middleware(slow_handler, mock_message, {})
        await middleware(fast_handler, mock_message, {})

        stats = middleware.get_stats()
        assert stats["total_requests"] == 3
        assert stats["timeouts"] == 1
        assert stats["timeout_rate"] == pytest.approx(33.33, rel=0.1)

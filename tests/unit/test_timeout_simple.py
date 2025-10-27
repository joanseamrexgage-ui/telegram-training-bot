"""
Simple tests for TimeoutMiddleware without markers.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from middlewares.timeout import TimeoutMiddleware


class TestTimeoutMiddlewareSimple:
    """Simple test suite for TimeoutMiddleware"""

    def test_basic_initialization(self):
        """Test basic middleware initialization."""
        middleware = TimeoutMiddleware(timeout=30)
        assert middleware.timeout == 30
        assert middleware.slow_threshold == 0.5
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["total_requests"] == 0

    @pytest.mark.asyncio
    async def test_basic_fast_handler(self):
        """Test basic fast handler execution."""
        middleware = TimeoutMiddleware(timeout=5)
        
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        result = await middleware(fast_handler, MagicMock(), {})
        assert result == "success"
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_basic_timeout(self):
        """Test basic timeout behavior."""
        middleware = TimeoutMiddleware(timeout=1)
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
            return "should_not_reach"
        
        result = await middleware(slow_handler, MagicMock(), {})
        assert result is None  # Should timeout
        assert middleware.stats["timeouts"] == 1
        assert middleware.stats["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_statistics_tracking(self):
        """Test statistics tracking."""
        middleware = TimeoutMiddleware(timeout=5)
        
        async def handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        # Execute multiple requests
        for _ in range(5):
            await middleware(handler, MagicMock(), {})
        
        stats = middleware.get_stats()
        assert stats["total_requests"] == 5
        assert stats["timeouts"] == 0
        assert stats["timeout_rate"] == 0.0
        assert stats["timeout_threshold"] == 5

    @pytest.mark.asyncio
    async def test_mixed_timeout_rate(self):
        """Test timeout rate calculation."""
        middleware = TimeoutMiddleware(timeout=2)
        
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "fast"
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
            return "slow"
        
        # 3 fast, 2 slow (timeout)
        await middleware(fast_handler, MagicMock(), {})
        await middleware(fast_handler, MagicMock(), {})
        await middleware(fast_handler, MagicMock(), {})
        await middleware(slow_handler, MagicMock(), {})
        await middleware(slow_handler, MagicMock(), {})
        
        stats = middleware.get_stats()
        assert stats["total_requests"] == 5
        assert stats["timeouts"] == 2
        assert stats["timeout_rate"] == 40.0  # 2/5 = 40%

    @pytest.mark.asyncio
    async def test_callback_query_timeout(self):
        """Test callback query timeout handling."""
        from aiogram.types import CallbackQuery
        middleware = TimeoutMiddleware(timeout=1)
        
        # Create a proper CallbackQuery mock
        callback_query = MagicMock(spec=CallbackQuery)
        callback_query.answer = AsyncMock()
        callback_query.from_user = MagicMock()
        callback_query.from_user.id = 12345
        callback_query.from_user.username = "testuser"
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)
            return "timeout"
        
        result = await middleware(slow_handler, callback_query, {})
        
        assert result is None
        callback_query.answer.assert_called_once()
        # Verify alert was shown
        call_args = callback_query.answer.call_args
        assert call_args[1].get("show_alert") is True

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        """Test that non-timeout exceptions are propagated."""
        middleware = TimeoutMiddleware(timeout=5)
        
        async def error_handler(event, data):
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await middleware(error_handler, MagicMock(), {})
        
        # Timeout count should not increase for non-timeout errors
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_statistics_reset(self):
        """Test statistics reset functionality."""
        middleware = TimeoutMiddleware(timeout=5)
        
        async def handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        # Generate some stats
        for _ in range(3):
            await middleware(handler, MagicMock(), {})
        
        # Reset stats
        middleware.reset_stats()
        
        # Verify stats are reset
        stats = middleware.get_stats()
        assert stats["total_requests"] == 0
        assert stats["timeouts"] == 0
        assert stats["timeout_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_slow_handler_detection(self):
        """Test slow handler warning detection."""
        middleware = TimeoutMiddleware(timeout=10, slow_threshold=0.3)
        
        async def slow_but_not_timeout_handler(event, data):
            # 3.5s is >30% of 10s timeout but doesn't trigger timeout
            await asyncio.sleep(3.5)
            return "completed"
        
        with patch('middlewares.timeout.logger') as mock_logger:
            result = await middleware(slow_but_not_timeout_handler, MagicMock(), {})
        
        assert result == "completed"
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["slow_handlers"] == 1

    @pytest.mark.asyncio
    async def test_health_status_healthy(self):
        """Test health status for healthy middleware."""
        middleware = TimeoutMiddleware(timeout=5)
        
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        # Only fast handlers
        for _ in range(20):
            await middleware(fast_handler, MagicMock(), {})
        
        health = middleware.get_health_status()
        assert health["status"] == "healthy"
        assert health["timeout_rate"] < 5.0

    @pytest.mark.asyncio
    async def test_health_status_critical(self):
        """Test health status for critical timeout rate."""
        middleware = TimeoutMiddleware(timeout=0.5)
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
        
        # All handlers timeout (100% timeout rate)
        for _ in range(10):
            await middleware(slow_handler, MagicMock(), {})
        
        health = middleware.get_health_status()
        assert health["status"] == "critical"
        assert health["timeout_rate"] == 100.0

    def test_string_representation(self):
        """Test string representation."""
        middleware = TimeoutMiddleware(timeout=30)
        repr_str = repr(middleware)
        
        assert "TimeoutMiddleware" in repr_str
        assert "timeout=30" in repr_str
        assert "requests=0" in repr_str
        assert "timeouts=0" in repr_str

    @pytest.mark.asyncio
    async def test_configure_threshold_validation(self):
        """Test threshold configuration validation."""
        middleware = TimeoutMiddleware()
        
        # Valid thresholds
        middleware.configure_threshold(0.0)
        assert middleware.slow_threshold == 0.0
        
        middleware.configure_threshold(1.0)
        assert middleware.slow_threshold == 1.0
        
        middleware.configure_threshold(0.5)
        assert middleware.slow_threshold == 0.5
        
        # Invalid thresholds
        with pytest.raises(ValueError):
            middleware.configure_threshold(-0.1)
        
        with pytest.raises(ValueError):
            middleware.configure_threshold(1.1)

    @pytest.mark.asyncio
    async def test_zero_timeout(self):
        """Test zero timeout behavior."""
        middleware = TimeoutMiddleware(timeout=0)
        
        async def any_handler(event, data):
            await asyncio.sleep(0.001)
            return "success"
        
        result = await middleware(any_handler, MagicMock(), {})
        assert result is None
        assert middleware.stats["timeouts"] == 1

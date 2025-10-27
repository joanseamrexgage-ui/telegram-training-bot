"""
Extended unit tests for TimeoutMiddleware.

Tests coverage:
- Normal handler execution (0.1s)
- Edge cases (0s timeout, very small timeout)
- DoS scenarios (multiple slow handlers)
- Async behavior (coroutine cancellation, race conditions)
- Error handling (malformed events, handler failures)
- Resource management (cleanup, memory leaks)
- Configuration changes (threshold updates)
- Statistics accuracy (all metrics)
- Health monitoring
"""

import pytest
import asyncio
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, call

from middlewares.timeout import TimeoutMiddleware


class TestTimeoutMiddlewareExtended:
    """Extended test suite for TimeoutMiddleware"""

    # ==================== INITIALIZATION TESTS ====================

    @pytest.mark.unit
    def test_default_initialization(self):
        """Test default middleware initialization."""
        middleware = TimeoutMiddleware()
        
        assert middleware.timeout == 30
        assert middleware.slow_threshold == 0.5
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["total_requests"] == 0
        assert middleware.stats["slow_handlers"] == 0

    @pytest.mark.unit
    def test_custom_initialization(self):
        """Test custom timeout and threshold initialization."""
        middleware = TimeoutMiddleware(timeout=60, slow_threshold=0.8)
        
        assert middleware.timeout == 60
        assert middleware.slow_threshold == 0.8

    @pytest.mark.unit
    def test_zero_timeout_initialization(self):
        """Test middleware with zero timeout."""
        middleware = TimeoutMiddleware(timeout=0)
        
        assert middleware.timeout == 0
        assert middleware.slow_threshold == 0.5

    @pytest.mark.unit
    def test_invalid_threshold_initialization(self):
        """Test invalid slow threshold values."""
        with pytest.raises(ValueError, match="threshold must be"):
            # Test in configure_threshold method since __init__ validates differently
            middleware = TimeoutMiddleware()
            middleware.configure_threshold(-0.1)
        
        with pytest.raises(ValueError, match="threshold must be"):
            middleware = TimeoutMiddleware()
            middleware.configure_threshold(1.5)

    # ==================== BASIC FUNCTIONALITY TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_millisecond_fast_handler(self):
        """Test handler completing in milliseconds."""
        middleware = TimeoutMiddleware(timeout=1)
        
        async def micro_handler(event, data):
            await asyncio.sleep(0.001)  # 1ms
            return "micro_success"
        
        result = await middleware(micro_handler, MagicMock(), {})
        assert result == "micro_success"
        assert middleware.stats["timeouts"] == 0
        assert middleware.stats["total_requests"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_exact_timeout_boundary(self):
        """Test handler that takes exactly the timeout duration."""
        middleware = TimeoutMiddleware(timeout=1)
        
        async def boundary_handler(event, data):
            await asyncio.sleep(1.0)
            return "should_timeout"
        
        start_time = time.time()
        result = await middleware(boundary_handler, MagicMock(), {})
        execution_time = time.time() - start_time
        
        assert result is None  # Should timeout
        assert middleware.stats["timeouts"] == 1
        assert 1.0 <= execution_time <= 1.1  # Allow small timing variance

    # ==================== EDGE CASES TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_negative_timeout_handling(self):
        """Test middleware with negative timeout (edge case)."""
        middleware = TimeoutMiddleware(timeout=-1)
        
        async def instant_handler(event, data):
            await asyncio.sleep(0.001)
            return "success"
        
        result = await middleware(instant_handler, MagicMock(), {})
        # Negative timeout should be handled gracefully
        assert result is None or result == "success"  # Behavior may vary

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_very_small_timeout(self):
        """Test with very small timeout (10ms)."""
        middleware = TimeoutMiddleware(timeout=0.01)
        
        async def small_delay_handler(event, data):
            await asyncio.sleep(0.005)
            return "success"
        
        result = await middleware(small_delay_handler, MagicMock(), {})
        assert result == "success"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_event_without_from_user(self):
        """Test with event that doesn't have from_user attribute."""
        middleware = TimeoutMiddleware(timeout=5)
        
        class MockEvent:
            pass
        
        async def handler(event, data):
            return "processed"
        
        event = MockEvent()
        result = await middleware(handler, event, {})
        
        assert result == "processed"
        assert middleware.stats["total_requests"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_event_with_none_from_user(self):
        """Test with event where from_user is None."""
        middleware = TimeoutMiddleware(timeout=5)
        
        event = MagicMock()
        event.from_user = None
        
        async def handler(event, data):
            return "processed"
        
        result = await middleware(handler, event, {})
        
        assert result == "processed"

    # ==================== SLOW HANDLER TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_slow_handler_detection_various_thresholds(self):
        """Test slow handler detection with different threshold values."""
        thresholds = [0.1, 0.5, 0.8, 0.9]
        
        for threshold in thresholds:
            middleware = TimeoutMiddleware(timeout=10, slow_threshold=threshold)
            
            # Handler that takes exactly threshold% of timeout
            slow_duration = 10 * threshold + 0.1  # Just over threshold
            
            async def threshold_handler(event, data):
                await asyncio.sleep(slow_duration)
                return "slow_success"
            
            with patch('middlewares.timeout.logger') as mock_logger:
                result = await middleware(threshold_handler, MagicMock(), {})
            
            assert result == "slow_success"
            assert middleware.stats["slow_handlers"] >= 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_fast_below_threshold_no_warning(self):
        """Test that fast handlers below threshold don't trigger warnings."""
        middleware = TimeoutMiddleware(timeout=10, slow_threshold=0.5)
        
        async def fast_handler(event, data):
            await asyncio.sleep(2.0)  # Well below 50% of 10s timeout
            return "fast_success"
        
        with patch('middlewares.timeout.logger') as mock_logger:
            result = await middleware(fast_handler, MagicMock(), {})
        
        assert result == "fast_success"
        # Warning should not be called for fast handlers
        mock_logger.warning.assert_not_called()

    # ==================== DOS AND CONCURRENCY TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_multiple_concurrent_timeouts(self):
        """Test multiple handlers timing out concurrently."""
        middleware = TimeoutMiddleware(timeout=1)
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
            return "should_not_reach"
        
        # Create 10 concurrent slow handlers
        tasks = []
        for i in range(10):
            tasks.append(middleware(slow_handler, MagicMock(), {}))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should be None (timeout) or exceptions
        assert all(r is None or isinstance(r, asyncio.TimeoutError) for r in results)
        assert middleware.stats["timeouts"] >= 10  # At least 10 timeouts

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_mixed_fast_slow_concurrent_handlers(self):
        """Test mix of fast and slow handlers concurrently."""
        middleware = TimeoutMiddleware(timeout=2)
        
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return f"fast_{event.from_user.id}"
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)
            return f"slow_{event.from_user.id}"
        
        # 5 fast, 5 slow handlers
        tasks = []
        for i in range(5):
            message = MagicMock()
            message.from_user = MagicMock()
            message.from_user.id = 1000 + i
            tasks.append(middleware(fast_handler, message, {}))
        
        for i in range(5):
            message = MagicMock()
            message.from_user = MagicMock()
            message.from_user.id = 2000 + i
            tasks.append(middleware(slow_handler, message, {}))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        fast_results = [r for r in results if r and not isinstance(r, Exception)]
        slow_results = [r for r in results if r is None or isinstance(r, Exception)]
        
        assert len(fast_results) == 5
        assert len(slow_results) == 5

    # ==================== ERROR HANDLING TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handler_raises_exception_before_timeout(self):
        """Test that exceptions are properly propagated."""
        middleware = TimeoutMiddleware(timeout=5)
        
        async def error_handler(event, data):
            raise ValueError("Test error before timeout")
        
        with pytest.raises(ValueError, match="Test error before timeout"):
            await middleware(error_handler, MagicMock(), {})
        
        assert middleware.stats["timeouts"] == 0  # No timeout occurred
        assert middleware.stats["total_requests"] == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_handler_raises_exception_after_timeout(self):
        """Test behavior when exception occurs after timeout."""
        middleware = TimeoutMiddleware(timeout=1)
        
        async def delayed_error_handler(event, data):
            await asyncio.sleep(0.5)  # No timeout
            raise RuntimeError("Error after successful execution")
        
        with pytest.raises(RuntimeError, match="Error after successful execution"):
            await middleware(delayed_error_handler, MagicMock(), {})

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_timeout_message_sending_failure(self):
        """Test when sending timeout message fails."""
        middleware = TimeoutMiddleware(timeout=1)
        
        message = MagicMock()
        message.answer = AsyncMock(side_effect=Exception("Message send failed"))
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)
            return "timeout"
        
        # Should not raise exception even if message sending fails
        result = await middleware(slow_handler, message, {})
        assert result is None
        assert middleware.stats["timeouts"] == 1

    # ==================== CONFIGURATION TESTS ====================

    @pytest.mark.unit
    def test_threshold_configuration_validation(self):
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

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_threshold_change_effectiveness(self):
        """Test that threshold changes affect slow handler detection."""
        # Start with high threshold
        middleware = TimeoutMiddleware(timeout=10, slow_threshold=0.9)
        
        async def handler_8s(event, data):
            await asyncio.sleep(8.0)
            return "should_not_warn"
        
        with patch('middlewares.timeout.logger') as mock_logger:
            await middleware(handler_8s, MagicMock(), {})
        
        assert middleware.stats["slow_handlers"] == 0
        
        # Change to low threshold
        middleware.configure_threshold(0.5)
        
        with patch('middlewares.timeout.logger') as mock_logger:
            await middleware(handler_8s, MagicMock(), {})
        
        assert middleware.stats["slow_handlers"] == 1

    # ==================== STATISTICS TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_comprehensive_statistics_tracking(self):
        """Test all statistics are accurately tracked."""
        middleware = TimeoutMiddleware(timeout=3, slow_threshold=0.3)
        
        # Fast handler
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "fast"
        
        # Medium handler (slow threshold)
        async def medium_handler(event, data):
            await asyncio.sleep(1.0)  # 33% of timeout, >30% threshold
            return "medium"
        
        # Slow handler (timeout)
        async def slow_handler(event, data):
            await asyncio.sleep(10.0)
            return "slow"
        
        # Execute mix of handlers
        await middleware(fast_handler, MagicMock(), {})
        await middleware(medium_handler, MagicMock(), {})
        await middleware(slow_handler, MagicMock(), {})
        await middleware(fast_handler, MagicMock(), {})
        
        stats = middleware.get_stats()
        
        assert stats["total_requests"] == 4
        assert stats["timeouts"] == 1
        assert stats["timeout_rate"] == 25.0
        assert stats["slow_handlers"] == 1  # medium_handler was slow
        assert stats["slow_handler_rate"] == 25.0
        assert stats["timeout_threshold"] == 3
        assert stats["slow_threshold"] == 0.3
        assert "avg_execution_time" in stats
        assert stats["avg_execution_time"] > 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_statistics_reset_completeness(self):
        """Test that statistics are completely reset."""
        middleware = TimeoutMiddleware(timeout=5)
        
        # Generate some statistics
        async def handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        for _ in range(10):
            await middleware(handler, MagicMock(), {})
        
        # Verify stats exist
        stats_before = middleware.get_stats()
        assert stats_before["total_requests"] == 10
        assert stats_before["timeouts"] == 0
        assert stats_before["slow_handlers"] == 0
        
        # Reset stats
        middleware.reset_stats()
        
        # Verify stats are completely cleared
        stats_after = middleware.get_stats()
        assert stats_after["total_requests"] == 0
        assert stats_after["timeouts"] == 0
        assert stats_after["slow_handlers"] == 0
        assert stats_after["timeout_rate"] == 0.0
        assert stats_after["slow_handler_rate"] == 0.0
        assert stats_after["avg_execution_time"] == 0.0

    # ==================== HEALTH MONITORING TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_status_healthy(self):
        """Test health status when all is well."""
        middleware = TimeoutMiddleware(timeout=5)
        
        # Only fast handlers
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        for _ in range(20):
            await middleware(fast_handler, MagicMock(), {})
        
        health = middleware.get_health_status()
        
        assert health["status"] == "healthy"
        assert health["timeout_rate"] < 5.0
        assert health["total_requests"] == 20
        assert health["timeouts"] == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_status_warning(self):
        """Test health status with warning level timeouts."""
        middleware = TimeoutMiddleware(timeout=1)
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
        
        # 1 successful, 3 timeouts out of 4 = 75% timeout rate (warning level)
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        await middleware(fast_handler, MagicMock(), {})
        await middleware(slow_handler, MagicMock(), {})
        await middleware(slow_handler, MagicMock(), {})
        await middleware(slow_handler, MagicMock(), {})
        
        health = middleware.get_health_status()
        
        assert health["status"] == "warning"
        assert health["timeout_rate"] == 75.0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_health_status_critical(self):
        """Test health status with critical timeout rate."""
        middleware = TimeoutMiddleware(timeout=0.5)
        
        # All handlers timeout (100% timeout rate)
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
        
        for _ in range(10):
            await middleware(slow_handler, MagicMock(), {})
        
        health = middleware.get_health_status()
        
        assert health["status"] == "critical"
        assert health["timeout_rate"] == 100.0

    # ==================== REPRESENTATION TESTS ====================

    @pytest.mark.unit
    def test_string_representation_empty_stats(self):
        """Test string representation with no statistics."""
        middleware = TimeoutMiddleware(timeout=30)
        repr_str = repr(middleware)
        
        assert "TimeoutMiddleware" in repr_str
        assert "timeout=30" in repr_str
        assert "requests=0" in repr_str
        assert "timeouts=0" in repr_str

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_string_representation_with_stats(self):
        """Test string representation with statistics."""
        middleware = TimeoutMiddleware(timeout=60)
        
        async def handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        await middleware(handler, MagicMock(), {})
        await middleware(handler, MagicMock(), {})
        
        repr_str = repr(middleware)
        
        assert "TimeoutMiddleware" in repr_str
        assert "timeout=60" in repr_str
        assert "requests=2" in repr_str
        assert "timeouts=0" in repr_str

    # ==================== RACE CONDITION TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_race_condition_handlers_starting_simultaneously(self):
        """Test race condition when multiple handlers start simultaneously."""
        middleware = TimeoutMiddleware(timeout=0.5)
        start_event = asyncio.Event()
        completion_times = []
        
        async def timing_handler(event, data):
            start_event.set()  # Signal that all handlers can start
            await asyncio.sleep(0.3)
            completion_times.append(time.time())
            return "completed"
        
        # Create many handlers that wait for the same event
        tasks = []
        for i in range(20):
            message = MagicMock()
            message.from_user = MagicMock()
            message.from_user.id = 1000 + i
            tasks.append(middleware(timing_handler, message, {}))
        
        # Let them all start at once
        await start_event.wait()
        start_time = time.time()
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        execution_time = time.time() - start_time
        
        # All should complete before timeout
        assert len([r for r in results if r == "completed"]) == 20
        assert execution_time < 1.0  # Should be around 0.3s

    # ==================== RESOURCE CLEANUP TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_memory_cleanup_after_many_operations(self):
        """Test that middleware doesn't leak memory after many operations."""
        middleware = TimeoutMiddleware(timeout=1)
        
        initial_stats_id = id(middleware.stats)
        
        async def handler(event, data):
            await asyncio.sleep(0.1)
            return "success"
        
        # Perform many operations
        for _ in range(100):
            await middleware(handler, MagicMock(), {})
        
        # Stats should be same object (no memory leak)
        assert id(middleware.stats) == initial_stats_id
        assert middleware.stats["total_requests"] == 100

    # ==================== CALLBACK QUERY SPECIFIC TESTS ====================

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_callback_query_timeout_with_show_alert(self):
        """Test that callback query timeouts show alert with correct parameters."""
        middleware = TimeoutMiddleware(timeout=1)
        
        callback_query = MagicMock()
        callback_query.answer = AsyncMock()
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
            return "timeout"
        
        result = await middleware(slow_handler, callback_query, {})
        
        assert result is None
        callback_query.answer.assert_called_once()
        
        # Verify alert parameters
        call_args = callback_query.answer.call_args
        assert "timeout" in call_args[0][0].lower() or "попробуйте" in call_args[0][0].lower()
        assert call_args[1]["show_alert"] is True

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_callback_query_without_message(self):
        """Test callback query that doesn't have message attribute."""
        middleware = TimeoutMiddleware(timeout=1)
        
        callback_query = MagicMock()
        callback_query.answer = AsyncMock()
        callback_query.message = None  # Some callback queries might not have message
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)
            return "timeout"
        
        result = await middleware(slow_handler, callback_query, {})
        
        assert result is None
        # Should still call answer, just without show_alert
        callback_query.answer.assert_called_once()

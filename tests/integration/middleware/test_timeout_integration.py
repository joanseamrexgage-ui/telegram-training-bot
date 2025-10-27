"""
Integration tests for TimeoutMiddleware pipeline integration.

Tests:
- Middleware pipeline with auth middleware
- Middleware pipeline with throttling middleware  
- FSM state management with timeout protection
- Multiple middleware interactions
- Error propagation through pipeline
- Performance impact of middleware stack
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Dict, Any

from middlewares.timeout import TimeoutMiddleware
from middlewares.auth import AuthMiddleware
from middlewares.throttling import ThrottlingMiddleware
from middlewares.database import DatabaseMiddleware


class TestTimeoutMiddlewareIntegration:
    """Integration test suite for TimeoutMiddleware pipeline"""

    # ==================== PIPELINE INTEGRATION TESTS ====================

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_with_auth_pipeline(self, mock_redis):
        """Test timeout middleware working with auth middleware."""
        # Setup middleware stack
        auth_middleware = AuthMiddleware(mock_redis, MagicMock())
        timeout_middleware = TimeoutMiddleware(timeout=3)
        
        # Mock authenticated event
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        event.from_user.username = "testuser"
        
        # Mock handler that simulates auth check then timeout
        async def authenticated_slow_handler(event, data):
            # Simulate authentication check
            await asyncio.sleep(0.1)
            # Simulate slow business logic
            await asyncio.sleep(5.0)  # Will timeout
            return "authenticated_result"
        
        # Create middleware pipeline
        async def pipeline_handler(handler, event, data):
            # Auth middleware processing
            await auth_middleware(handler, event, data)
            # Timeout middleware processing
            return await timeout_middleware(handler, event, data)
        
        result = await pipeline_handler(authenticated_slow_handler, event, {})
        
        # Result should be None due to timeout
        assert result is None
        assert timeout_middleware.stats["timeouts"] == 1
        assert timeout_middleware.stats["total_requests"] == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_with_throttling_pipeline(self, mock_redis):
        """Test timeout middleware working with throttling middleware."""
        throttling_middleware = ThrottlingMiddleware(mock_redis)
        timeout_middleware = TimeoutMiddleware(timeout=2)
        
        # Track throttling state
        throttling_middleware.state = {}
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        async def handler_with_throttling(event, data):
            await asyncio.sleep(0.5)
            return "processed"
        
        # Test: First call should work
        result = await throttling_middleware(handler_with_throttling, event, {})
        assert result == "processed"
        
        # Apply timeout protection
        timeout_result = await timeout_middleware(handler_with_throttling, event, {})
        assert timeout_result == "processed"
        
        # Statistics should reflect both middleware usage
        assert timeout_middleware.stats["total_requests"] == 1
        assert timeout_middleware.stats["timeouts"] == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_with_database_pipeline(self, mock_db_session):
        """Test timeout middleware working with database middleware."""
        db_middleware = DatabaseMiddleware(MagicMock())
        db_middleware.session = mock_db_session
        timeout_middleware = TimeoutMiddleware(timeout=3)
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        async def db_handler_with_timeout(event, data):
            # Simulate database operation
            await asyncio.sleep(0.2)
            # Simulate slow business logic that times out
            await asyncio.sleep(5.0)
            return "database_result"
        
        # Create pipeline: DB -> Timeout
        async def db_timeout_pipeline(handler, event, data):
            await db_middleware(handler, event, data)
            return await timeout_middleware(handler, event, data)
        
        result = await db_timeout_pipeline(db_handler_with_timeout, event, {})
        
        assert result is None  # Should timeout
        assert timeout_middleware.stats["timeouts"] == 1

    # ==================== FULL PIPELINE TESTS ====================

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_complete_middleware_pipeline(self, mock_redis, mock_db_session):
        """Test complete middleware pipeline: Auth -> Database -> Throttling -> Timeout."""
        # Setup all middleware
        auth_middleware = AuthMiddleware(mock_redis, MagicMock())
        db_middleware = DatabaseMiddleware(MagicMock())
        db_middleware.session = mock_db_session
        throttling_middleware = ThrottlingMiddleware(mock_redis)
        timeout_middleware = TimeoutMiddleware(timeout=2)
        
        # Mock authenticated user
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        event.from_user.username = "testuser"
        
        async def complex_handler(event, data):
            # Simulate authentication
            await asyncio.sleep(0.1)
            # Simulate database operation
            await asyncio.sleep(0.1)
            # Simulate business logic
            await asyncio.sleep(0.1)
            return "complex_result"
        
        # Complete pipeline
        async def full_pipeline(handler, event, data):
            # Auth first
            await auth_middleware(handler, event, data)
            # Database
            await db_middleware(handler, event, data)
            # Throttling
            await throttling_middleware(handler, event, data)
            # Timeout protection
            return await timeout_middleware(handler, event, data)
        
        result = await full_pipeline(complex_handler, event, {})
        assert result == "complex_result"
        
        # Verify all middleware processed
        assert timeout_middleware.stats["total_requests"] == 1
        assert timeout_middleware.stats["timeouts"] == 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_with_timeout_in_middle(self, mock_redis, mock_db_session):
        """Test timeout occurring in middle of pipeline."""
        auth_middleware = AuthMiddleware(mock_redis, MagicMock())
        timeout_middleware = TimeoutMiddleware(timeout=1)
        db_middleware = DatabaseMiddleware(MagicMock())
        db_middleware.session = mock_db_session
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        async def slow_handler(event, data):
            await asyncio.sleep(0.5)  # Auth completes
            await asyncio.sleep(2.0)  # Database starts, will timeout
            return "should_not_reach"
        
        # Pipeline where timeout happens during DB operation
        async def pipeline_with_timeout(handler, event, data):
            await auth_middleware(handler, event, data)
            # Start DB operation
            db_task = asyncio.create_task(db_middleware(handler, event, data))
            timeout_task = asyncio.create_task(timeout_middleware(db_task, event, data))
            return await timeout_task
        
        result = await pipeline_with_timeout(slow_handler, event, {})
        assert result is None  # Timeout occurred
        assert timeout_middleware.stats["timeouts"] == 1

    # ==================== FSM STATE INTEGRATION TESTS ====================

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_with_fsm_states(self):
        """Test timeout middleware preserving FSM state management."""
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.state import State
        
        timeout_middleware = TimeoutMiddleware(timeout=1)
        
        # Mock FSM context
        fsm_context = MagicMock(spec=FSMContext)
        fsm_context.get_state = AsyncMock(return_value="waiting_for_input")
        fsm_context.set_state = AsyncMock()
        
        # Mock event with FSM data
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        data = {"fsm_context": fsm_context}
        
        async def fsm_slow_handler(event, data):
            # Simulate FSM state check
            state = await data["fsm_context"].get_state()
            assert state == "waiting_for_input"
            
            # Simulate slow processing
            await asyncio.sleep(5.0)  # Will timeout
            
            # Update FSM state (should not execute due to timeout)
            await data["fsm_context"].set_state("completed")
            return "fsm_result"
        
        result = await timeout_middleware(fsm_slow_handler, event, data)
        
        assert result is None  # Timeout occurred
        assert timeout_middleware.stats["timeouts"] == 1
        
        # FSM state should not be updated due to timeout
        fsm_context.set_state.assert_not_called()

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_preserving_fsm_on_success(self):
        """Test that successful handler execution preserves FSM state."""
        from aiogram.fsm.context import FSMContext
        
        timeout_middleware = TimeoutMiddleware(timeout=5)
        
        fsm_context = MagicMock(spec=FSMContext)
        fsm_context.get_state = AsyncMock(return_state="processing")
        fsm_context.set_state = AsyncMock()
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        data = {"fsm_context": fsm_context}
        
        async def fsm_fast_handler(event, data):
            # Check FSM state
            state = await data["fsm_context"].get_state()
            assert state == "processing"
            
            # Update FSM state
            await data["fsm_context"].set_state("completed")
            return "fsm_success"
        
        result = await timeout_middleware(fsm_fast_handler, event, data)
        
        assert result == "fsm_success"
        assert timeout_middleware.stats["timeouts"] == 0
        
        # FSM state should be updated successfully
        fsm_context.set_state.assert_called_once_with("completed")

    # ==================== ERROR PROPAGATION TESTS ====================

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_error_propagation_through_pipeline(self, mock_redis):
        """Test that errors propagate correctly through middleware pipeline."""
        auth_middleware = AuthMiddleware(mock_redis, MagicMock())
        timeout_middleware = TimeoutMiddleware(timeout=5)
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        async def error_in_pipeline_handler(event, data):
            await asyncio.sleep(0.1)
            raise ValueError("Pipeline error")
        
        async def pipeline_with_error(handler, event, data):
            await auth_middleware(handler, event, data)
            return await timeout_middleware(handler, event, data)
        
        with pytest.raises(ValueError, match="Pipeline error"):
            await pipeline_with_error(error_in_pipeline_handler, event, {})
        
        # Timeout count should not increase for non-timeout errors
        assert timeout_middleware.stats["timeouts"] == 0
        assert timeout_middleware.stats["total_requests"] == 1

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_then_error_in_cleanup(self, mock_redis):
        """Test handling when timeout occurs but cleanup raises error."""
        timeout_middleware = TimeoutMiddleware(timeout=1)
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        # Mock event answer to fail
        event.answer = AsyncMock(side_effect=ConnectionError("Failed to send"))
        
        async def slow_handler(event, data):
            await asyncio.sleep(5.0)  # Will timeout
            return "should_not_reach"
        
        # Should handle cleanup error gracefully
        result = await timeout_middleware(slow_handler, event, {})
        
        assert result is None
        assert timeout_middleware.stats["timeouts"] == 1

    # ==================== PERFORMANCE IMPACT TESTS ====================

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_middleware_stack_performance_impact(self):
        """Test performance impact of middleware stack."""
        timeout_middleware = TimeoutMiddleware(timeout=10)
        
        # Multiple middleware layers
        middleware_layers = [
            lambda handler, event, data: handler(event, data),
            lambda handler, event, data: handler(event, data),
            lambda handler, event, data: handler(event, data)
        ]
        
        async def simple_handler(event, data):
            await asyncio.sleep(0.01)
            return "simple"
        
        # Baseline: handler alone
        start_time = time.time()
        for _ in range(100):
            await simple_handler(MagicMock(), {})
        baseline_time = time.time() - start_time
        
        # With middleware stack
        start_time = time.time()
        for _ in range(100):
            result = simple_handler(MagicMock(), {})
            for middleware in middleware_layers:
                result = middleware(result, MagicMock(), {})
            await timeout_middleware(simple_handler, MagicMock(), {})
        middleware_time = time.time() - start_time
        
        # Middleware should not add too much overhead
        overhead_ratio = middleware_time / baseline_time
        assert overhead_ratio < 2.0  # Less than 2x overhead acceptable

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_timeout_statistics_accuracy_in_pipeline(self, mock_redis):
        """Test that timeout statistics are accurate in complex pipeline."""
        auth_middleware = AuthMiddleware(mock_redis, MagicMock())
        timeout_middleware = TimeoutMiddleware(timeout=1)
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        async def fast_handler(event, data):
            await asyncio.sleep(0.1)
            return "fast"
        
        async def slow_handler(event, data):
            await asyncio.sleep(3.0)  # Will timeout
            return "slow"
        
        async def error_handler(event, data):
            await asyncio.sleep(0.1)
            raise ValueError("Test error")
        
        # Pipeline that processes different types of handlers
        async def pipeline(handler, event, data):
            await auth_middleware(handler, event, data)
            return await timeout_middleware(handler, event, data)
        
        # Process mix of handlers
        await pipeline(fast_handler, event, {})
        await pipeline(fast_handler, event, {})
        await pipeline(slow_handler, event, {})
        await pipeline(fast_handler, event, {})
        
        with pytest.raises(ValueError):
            await pipeline(error_handler, event, {})
        
        # Check statistics accuracy
        stats = timeout_middleware.get_stats()
        assert stats["total_requests"] == 5  # Total requests processed
        assert stats["timeouts"] == 1  # Only slow_handler timed out
        assert stats["timeout_rate"] == 20.0  # 1/5 = 20%
        assert stats["slow_handlers"] == 0  # No slow handlers (fast < threshold)

    # ==================== CONCURRENT PIPELINE TESTS ====================

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_concurrent_pipeline_requests(self, mock_redis):
        """Test multiple concurrent requests through pipeline."""
        auth_middleware = AuthMiddleware(mock_redis, MagicMock())
        timeout_middleware = TimeoutMiddleware(timeout=2)
        
        async def pipeline_handler(handler, event, data):
            await auth_middleware(handler, event, data)
            return await timeout_middleware(handler, event, data)
        
        async def variable_handler(event, data):
            duration = data.get("duration", 0.5)
            await asyncio.sleep(duration)
            return f"completed_in_{duration}s"
        
        # Create 20 concurrent requests with different durations
        tasks = []
        for i in range(20):
            event = MagicMock()
            event.from_user = MagicMock()
            event.from_user.id = 1000 + i
            
            duration = 0.5 + (i % 5) * 0.3  # 0.5s to 1.7s
            data = {"duration": duration}
            
            task = pipeline_handler(variable_handler, event, data)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify results
        successful_results = [r for r in results if isinstance(r, str)]
        timeout_results = [r for r in results if r is None]
        
        # Should have 5 timeouts (requests > 2s) and 15 successful
        assert len(successful_results) == 15
        assert len(timeout_results) == 5
        assert timeout_middleware.stats["timeouts"] == 5

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_pipeline_middleware_exception_handling(self, mock_redis):
        """Test middleware exceptions in pipeline context."""
        auth_middleware = AuthMiddleware(mock_redis, MagicMock())
        timeout_middleware = TimeoutMiddleware(timeout=5)
        
        # Mock auth to raise exception
        auth_middleware.authenticate = MagicMock(side_effect=PermissionError("Auth failed"))
        
        event = MagicMock()
        event.from_user = MagicMock()
        event.from_user.id = 12345
        
        async def handler(event, data):
            return "should_not_reach"
        
        async def pipeline_with_failing_auth(handler, event, data):
            await auth_middleware(handler, event, data)
            return await timeout_middleware(handler, event, data)
        
        with pytest.raises(PermissionError, match="Auth failed"):
            await pipeline_with_failing_auth(handler, event, {})
        
        # Timeout middleware should not process due to early exception
        assert timeout_middleware.stats["total_requests"] == 0

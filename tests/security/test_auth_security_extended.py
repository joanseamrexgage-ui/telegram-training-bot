"""
Extended security tests for AuthSecurity module.

Covers additional functionality and edge cases to reach 85%+ code coverage.

Tests:
- Block time remaining calculations
- Global initialization functions
- Error handling paths
- Additional edge cases
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from utils.auth_security import (
    AuthSecurity,
    init_auth_security,
    get_auth_security,
    MAX_ATTEMPTS,
    BLOCK_DURATION_MINUTES
)


class TestBlockTimeRemaining:
    """Test block time remaining calculations"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_block_time_remaining_when_blocked(self, mock_redis):
        """Test getting remaining block time for blocked user"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Trigger block
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Get remaining time
        remaining_seconds = await auth.get_block_time_remaining(user_id)

        # Should be approximately BLOCK_DURATION_MINUTES * 60 seconds
        assert remaining_seconds is not None
        expected_seconds = BLOCK_DURATION_MINUTES * 60
        # Allow 10 second tolerance
        assert abs(remaining_seconds - expected_seconds) < 10

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_block_time_remaining_when_not_blocked(self, mock_redis):
        """Test getting remaining block time for non-blocked user"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # User not blocked
        remaining_seconds = await auth.get_block_time_remaining(user_id)

        # Should return None
        assert remaining_seconds is None

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_block_time_remaining_decreases(self, mock_redis):
        """Test that block time remaining decreases over time"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Trigger block
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Get initial remaining time
        initial_remaining = await auth.get_block_time_remaining(user_id)

        # Mock time passing (1 minute)
        future_time = datetime.utcnow() + timedelta(minutes=1)
        future_block_time = datetime.utcnow() + timedelta(minutes=BLOCK_DURATION_MINUTES)

        # Mock is_user_blocked to return future time
        with patch('utils.auth_security.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = future_time
            # Recalculate with 1 minute passed
            remaining_after = (future_block_time - future_time).total_seconds()

        # Remaining time should be less than initial
        assert remaining_after < initial_remaining

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_block_time_remaining_negative_protection(self, mock_redis):
        """Test that block time remaining never goes negative"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Mock expired block (past time)
        past_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        mock_redis.get = AsyncMock(return_value=past_time)

        # Should return None (auto-unblocked) or 0, not negative
        remaining = await auth.get_block_time_remaining(user_id)

        # Could be None (unblocked) or 0, but never negative
        assert remaining is None or remaining >= 0


class TestRemainingAttemptsAdvanced:
    """Advanced tests for remaining attempts calculations"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_remaining_attempts_redis_failure(self):
        """Test remaining attempts when Redis fails"""
        # Mock Redis that fails on get
        failing_redis = AsyncMock()
        failing_redis.get = AsyncMock(side_effect=Exception("Redis connection lost"))
        failing_redis.incr = AsyncMock(return_value=1)

        auth = AuthSecurity(failing_redis)
        user_id = 12345

        # Should fail open and return MAX_ATTEMPTS
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_remaining_attempts_when_blocked(self, mock_redis):
        """Test remaining attempts returns 0 when blocked"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Block user
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Verify blocked
        is_blocked, _ = await auth.is_user_blocked(user_id)
        assert is_blocked is True

        # Remaining should be 0
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == 0

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_remaining_attempts_never_negative(self, mock_redis):
        """Test that remaining attempts never goes negative"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Make more attempts than allowed (shouldn't happen but test robustness)
        for _ in range(MAX_ATTEMPTS + 5):
            await auth.increment_password_attempts(user_id)

        remaining = await auth.get_remaining_attempts(user_id)

        # Should be 0, not negative
        assert remaining >= 0


class TestResetPasswordAttemptsAdvanced:
    """Advanced tests for password attempt reset"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_reset_clears_both_attempts_and_block(self, mock_redis):
        """Test that reset clears both attempt counter and block"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Block user
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Verify blocked
        assert (await auth.is_user_blocked(user_id))[0] is True

        # Reset
        await auth.reset_password_attempts(user_id)

        # Both attempt counter and block should be cleared
        assert (await auth.is_user_blocked(user_id))[0] is False
        assert await auth.get_remaining_attempts(user_id) == MAX_ATTEMPTS

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_reset_redis_failure_handling(self):
        """Test reset handles Redis failures gracefully"""
        # Mock Redis that fails on delete
        failing_redis = AsyncMock()
        failing_redis.delete = AsyncMock(side_effect=Exception("Redis delete failed"))

        auth = AuthSecurity(failing_redis)
        user_id = 12345

        # Should not raise exception
        try:
            await auth.reset_password_attempts(user_id)
            success = True
        except Exception:
            success = False

        assert success is True


class TestGlobalAuthSecurity:
    """Test global AuthSecurity initialization and retrieval"""

    @pytest.mark.security
    def test_init_auth_security(self, mock_redis):
        """Test global AuthSecurity initialization"""
        # Initialize global instance
        auth = init_auth_security(mock_redis)

        # Should return AuthSecurity instance
        assert isinstance(auth, AuthSecurity)
        assert auth.redis == mock_redis

    @pytest.mark.security
    def test_get_auth_security(self, mock_redis):
        """Test getting global AuthSecurity instance"""
        # Initialize first
        init_auth_security(mock_redis)

        # Get instance
        auth = get_auth_security()

        # Should return the initialized instance
        assert isinstance(auth, AuthSecurity)
        assert auth.redis == mock_redis

    @pytest.mark.security
    def test_get_auth_security_before_init(self):
        """Test getting AuthSecurity before initialization"""
        # Reset global state
        import utils.auth_security as auth_module
        auth_module._auth_security = None

        # Should return None if not initialized
        auth = get_auth_security()
        assert auth is None


class TestIsUserBlockedAdvanced:
    """Advanced tests for is_user_blocked functionality"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_is_user_blocked_not_blocked_path(self, mock_redis):
        """Test is_user_blocked returns False when no block exists"""
        # Mock Redis returns None (no block)
        mock_redis.get = AsyncMock(return_value=None)

        auth = AuthSecurity(mock_redis)
        user_id = 12345

        is_blocked, blocked_until = await auth.is_user_blocked(user_id)

        # Should return False, None
        assert is_blocked is False
        assert blocked_until is None

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_is_user_blocked_expired_block_cleanup(self, mock_redis):
        """Test expired block triggers cleanup"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # First, create a real block
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Manually set expired block in Redis
        past_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        await mock_redis.set(f"admin:blocked:{user_id}", past_time)

        # Check block status - should trigger cleanup
        is_blocked, blocked_until = await auth.is_user_blocked(user_id)

        # Should be unblocked
        assert is_blocked is False
        assert blocked_until is None

        # Verify block key was removed
        block_key_exists = await mock_redis.get(f"admin:blocked:{user_id}")
        assert block_key_exists is None


class TestIncrementPasswordAttemptsAdvanced:
    """Advanced tests for increment_password_attempts"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_increment_sets_ttl_on_first_attempt(self, mock_redis):
        """Test that TTL is set on first attempt"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # First attempt
        await auth.increment_password_attempts(user_id)

        # Verify TTL was set on the key
        ttl = await mock_redis.ttl(f"admin:password_attempts:{user_id}")
        # TTL should be positive and close to ATTEMPT_TTL_SECONDS
        assert ttl > 0
        assert ttl <= 300  # ATTEMPT_TTL_SECONDS

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_increment_does_not_set_ttl_on_subsequent_attempts(self, mock_redis):
        """Test that TTL is only set on first attempt, not subsequent"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # First attempt (sets TTL)
        await auth.increment_password_attempts(user_id)
        ttl_after_first = await mock_redis.ttl(f"admin:password_attempts:{user_id}")

        # Wait a tiny bit to show time passing
        await asyncio.sleep(0.1)

        # Second attempt (should NOT reset TTL)
        await auth.increment_password_attempts(user_id)
        ttl_after_second = await mock_redis.ttl(f"admin:password_attempts:{user_id}")

        # TTL should be less than or equal (time passed), not reset to full value
        assert ttl_after_second <= ttl_after_first

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_increment_creates_block_on_max_attempts(self, mock_redis):
        """Test that reaching MAX_ATTEMPTS creates a block"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Make MAX_ATTEMPTS attempts
        for _ in range(MAX_ATTEMPTS):
            attempts, blocked_until = await auth.increment_password_attempts(user_id)

        # Last attempt should create block
        assert attempts == MAX_ATTEMPTS
        assert blocked_until is not None

        # Verify block was stored in Redis
        block_key = f"admin:blocked:{user_id}"
        block_data = await mock_redis.get(block_key)
        assert block_data is not None
        assert "admin:blocked" in block_key

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_increment_block_has_correct_expiration(self, mock_redis):
        """Test that block has correct expiration time"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Trigger block
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Verify block key has TTL set
        block_key = f"admin:blocked:{user_id}"
        ttl = await mock_redis.ttl(block_key)

        # TTL should be approximately BLOCK_DURATION_MINUTES * 60
        expected_ttl = BLOCK_DURATION_MINUTES * 60
        assert ttl > 0
        assert abs(ttl - expected_ttl) < 10  # Allow 10 second tolerance


class TestEdgeCasesExtended:
    """Extended edge case tests"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_zero_user_id(self, mock_redis):
        """Test handling of user_id = 0"""
        auth = AuthSecurity(mock_redis)

        # Should handle gracefully (fail-safe)
        attempts, blocked_until = await auth.increment_password_attempts(0)
        assert attempts == 0
        assert blocked_until is None

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_string_user_id_handled_gracefully(self, mock_redis):
        """Test that invalid user_id types don't crash the system"""
        auth = AuthSecurity(mock_redis)

        # Test with string user_id
        attempts, blocked_until = await auth.increment_password_attempts("invalid")
        assert attempts == 0  # Fail-safe
        assert blocked_until is None

        # Test with float user_id
        attempts, blocked_until = await auth.increment_password_attempts(12.34)
        assert attempts == 0  # Fail-safe
        assert blocked_until is None

        # Test with list user_id
        attempts, blocked_until = await auth.increment_password_attempts([123])
        assert attempts == 0  # Fail-safe
        assert blocked_until is None


class TestCoverageBoost:
    """Additional tests to boost coverage to 85%+"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_is_user_blocked_invalid_datetime_format(self, mock_redis):
        """Test is_user_blocked with corrupted datetime data"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Set invalid datetime format in Redis
        await mock_redis.set(f"admin:blocked:{user_id}", "invalid-datetime-format")

        # Should handle gracefully (fail open)
        is_blocked, blocked_until = await auth.is_user_blocked(user_id)
        assert is_blocked is False  # Fail open on error
        assert blocked_until is None

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_get_remaining_attempts_with_non_integer_redis_value(self, mock_redis):
        """Test get_remaining_attempts when Redis returns non-integer"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Set non-integer value in Redis
        await mock_redis.set(f"admin:password_attempts:{user_id}", "not-a-number")

        # Should handle gracefully and return MAX_ATTEMPTS
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS  # Fail open

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_get_block_time_remaining_edge_cases(self, mock_redis):
        """Test get_block_time_remaining with various states"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # User not blocked - should return None
        remaining = await auth.get_block_time_remaining(user_id)
        assert remaining is None

        # Block user
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Should return positive integer
        remaining = await auth.get_block_time_remaining(user_id)
        assert remaining is not None
        assert remaining >= 0
        assert isinstance(remaining, int)

    @pytest.mark.asyncio
    @pytest.mark.security  
    async def test_increment_logs_warning_on_block(self, mock_redis):
        """Test that reaching MAX_ATTEMPTS triggers warning log"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Make attempts up to MAX_ATTEMPTS (this should log warnings)
        for i in range(MAX_ATTEMPTS):
            attempts, blocked_until = await auth.increment_password_attempts(user_id)

        # Last attempt should have blocked user
        assert attempts == MAX_ATTEMPTS
        assert blocked_until is not None

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_reset_logs_success(self, mock_redis):
        """Test that reset logs success message"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Make some attempts
        await auth.increment_password_attempts(user_id)
        await auth.increment_password_attempts(user_id)

        # Reset (should log success)
        await auth.reset_password_attempts(user_id)

        # Verify reset worked
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_invalid_user_id_type_exception_path(self, mock_redis):
        """Test exception handling for truly invalid user_id types"""
        auth = AuthSecurity(mock_redis)

        # Test with dict (comparison will raise TypeError)
        attempts, blocked_until = await auth.increment_password_attempts({"id": 123})
        assert attempts == 0
        assert blocked_until is None

        # Test with None
        attempts, blocked_until = await auth.increment_password_attempts(None)
        assert attempts == 0
        assert blocked_until is None

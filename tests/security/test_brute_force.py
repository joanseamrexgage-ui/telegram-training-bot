"""
Security tests for brute-force protection.

Tests BLOCKER-002: Redis-backed password attempt tracking.

Tests:
- Password attempt counting
- Block persistence across restarts
- Block expiration
- Concurrent attack attempts
- Reset functionality
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from utils.auth_security import AuthSecurity, MAX_ATTEMPTS, BLOCK_DURATION_MINUTES


class TestBruteForceProtection:
    """Test suite for brute-force protection"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_password_attempts_tracking(self, mock_redis):
        """Test Redis-backed password attempt counting"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # First attempt
        attempts, blocked_until = await auth.increment_password_attempts(user_id)
        assert attempts == 1
        assert blocked_until is None

        # Second attempt
        attempts, blocked_until = await auth.increment_password_attempts(user_id)
        assert attempts == 2
        assert blocked_until is None

        # Third attempt - should trigger block
        attempts, blocked_until = await auth.increment_password_attempts(user_id)
        assert attempts == 3
        assert blocked_until is not None
        assert blocked_until > datetime.utcnow()

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_block_persistence(self, mock_redis):
        """Test blocks persist across bot restarts"""
        auth1 = AuthSecurity(mock_redis)
        user_id = 12345

        # Trigger block with first instance
        for _ in range(MAX_ATTEMPTS):
            await auth1.increment_password_attempts(user_id)

        # Simulate restart with new instance (but same Redis)
        auth2 = AuthSecurity(mock_redis)
        is_blocked, remaining = await auth2.is_user_blocked(user_id)

        assert is_blocked is True
        assert remaining is not None

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_remaining_attempts_countdown(self, mock_redis):
        """Test remaining attempts calculation"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Initial state
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS

        # After 1 attempt
        await auth.increment_password_attempts(user_id)
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS - 1

        # After 2 attempts
        await auth.increment_password_attempts(user_id)
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS - 2

        # After 3 attempts (blocked)
        await auth.increment_password_attempts(user_id)
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == 0

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_successful_login_resets_attempts(self, mock_redis):
        """Test that successful login clears attempt counter"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Make 2 failed attempts
        await auth.increment_password_attempts(user_id)
        await auth.increment_password_attempts(user_id)

        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == 1

        # Successful login
        await auth.reset_password_attempts(user_id)

        # Attempts should be reset
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS

        is_blocked, _ = await auth.is_user_blocked(user_id)
        assert is_blocked is False

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_multiple_users_independent_tracking(self, mock_redis):
        """Test that different users have independent attempt tracking"""
        auth = AuthSecurity(mock_redis)
        user1 = 11111
        user2 = 22222

        # User 1 makes 2 attempts
        await auth.increment_password_attempts(user1)
        await auth.increment_password_attempts(user1)

        # User 2 makes 3 attempts (blocked)
        for _ in range(3):
            await auth.increment_password_attempts(user2)

        # Check user 1 - should have 1 remaining
        remaining1 = await auth.get_remaining_attempts(user1)
        is_blocked1, _ = await auth.is_user_blocked(user1)
        assert remaining1 == 1
        assert is_blocked1 is False

        # Check user 2 - should be blocked
        remaining2 = await auth.get_remaining_attempts(user2)
        is_blocked2, _ = await auth.is_user_blocked(user2)
        assert remaining2 == 0
        assert is_blocked2 is True

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_block_duration(self, mock_redis):
        """Test that block duration is correctly set"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Trigger block
        for _ in range(MAX_ATTEMPTS):
            attempts, blocked_until = await auth.increment_password_attempts(user_id)

        # blocked_until should be approximately BLOCK_DURATION_MINUTES from now
        assert blocked_until is not None

        time_diff = blocked_until - datetime.utcnow()
        expected_duration = timedelta(minutes=BLOCK_DURATION_MINUTES)

        # Allow 10 second tolerance for test execution time
        assert abs(time_diff.total_seconds() - expected_duration.total_seconds()) < 10

    @pytest.mark.asyncio
    @pytest.mark.security
    @pytest.mark.slow
    async def test_concurrent_attack_attempts(self, mock_redis):
        """Test concurrent attack attempts from multiple sources"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Simulate 10 concurrent login attempts
        tasks = [
            auth.increment_password_attempts(user_id)
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed without errors
        assert all(not isinstance(r, Exception) for r in results)

        # User should be blocked
        is_blocked, _ = await auth.is_user_blocked(user_id)
        assert is_blocked is True

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_failed_attempts_not_user_blocked(self, mock_redis):
        """Test user not blocked before reaching limit"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Make MAX_ATTEMPTS - 1 attempts
        for _ in range(MAX_ATTEMPTS - 1):
            await auth.increment_password_attempts(user_id)

        # Should not be blocked yet
        is_blocked, _ = await auth.is_user_blocked(user_id)
        assert is_blocked is False

        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == 1

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_redis_failure_fail_open(self):
        """Test fail-open behavior when Redis is unavailable"""
        # Mock Redis that always fails
        failing_redis = AsyncMock()
        failing_redis.incr = AsyncMock(side_effect=Exception("Redis down"))
        failing_redis.get = AsyncMock(side_effect=Exception("Redis down"))
        failing_redis.set = AsyncMock(side_effect=Exception("Redis down"))
        failing_redis.delete = AsyncMock(side_effect=Exception("Redis down"))

        auth = AuthSecurity(failing_redis)
        user_id = 12345

        # Should not raise exception, but fail open (allow access)
        attempts, blocked_until = await auth.increment_password_attempts(user_id)
        assert attempts == 0  # Fail-open returns 0 attempts
        assert blocked_until is None

        is_blocked, _ = await auth.is_user_blocked(user_id)
        # Fail-open should allow access
        assert is_blocked is False

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_block_expiration_auto_unblock(self, mock_redis):
        """Test that expired blocks automatically unblock users"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Trigger block
        for _ in range(MAX_ATTEMPTS):
            await auth.increment_password_attempts(user_id)

        # Verify blocked
        is_blocked, blocked_until = await auth.is_user_blocked(user_id)
        assert is_blocked is True

        # Mock Redis to return expired block time
        past_time = (datetime.utcnow() - timedelta(minutes=10)).isoformat()
        mock_redis.get = AsyncMock(return_value=past_time)

        # Check again - should auto-unblock
        is_blocked, _ = await auth.is_user_blocked(user_id)
        assert is_blocked is False

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_attack_rate_limiting_effectiveness(self, mock_redis):
        """Test that brute-force protection slows down attackers"""
        auth = AuthSecurity(mock_redis)
        user_id = 12345

        # Simulate attacker trying 100 attempts
        successful_attempts = 0
        blocked_attempts = 0

        for i in range(100):
            is_blocked, _ = await auth.is_user_blocked(user_id)

            if not is_blocked:
                await auth.increment_password_attempts(user_id)
                successful_attempts += 1
            else:
                blocked_attempts += 1

        # Should only allow MAX_ATTEMPTS before blocking
        assert successful_attempts == MAX_ATTEMPTS
        assert blocked_attempts == 100 - MAX_ATTEMPTS

        # Attacker effectiveness severely reduced
        attack_effectiveness = successful_attempts / 100
        assert attack_effectiveness <= 0.05  # Max 5% success rate


class TestAuthSecurityEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_invalid_user_id(self, mock_redis):
        """Test handling of invalid user IDs"""
        auth = AuthSecurity(mock_redis)

        # Should not crash on invalid user_id
        attempts, blocked_until = await auth.increment_password_attempts(None)
        assert attempts == 0  # Fail-safe

        is_blocked, _ = await auth.is_user_blocked(None)
        assert is_blocked is False  # Fail-open for invalid input

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_negative_user_id(self, mock_redis):
        """Test handling of negative user IDs"""
        auth = AuthSecurity(mock_redis)
        invalid_user = -12345

        # Should handle gracefully
        attempts, _ = await auth.increment_password_attempts(invalid_user)
        remaining = await auth.get_remaining_attempts(invalid_user)

        # Should still track (Telegram IDs can't be negative but test robustness)
        assert isinstance(attempts, int)
        assert isinstance(remaining, int)

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_very_large_user_id(self, mock_redis):
        """Test handling of very large user IDs"""
        auth = AuthSecurity(mock_redis)
        large_user = 9999999999999

        # Should handle without overflow
        attempts, _ = await auth.increment_password_attempts(large_user)
        assert attempts == 1

    @pytest.mark.asyncio
    @pytest.mark.security
    async def test_reset_non_existent_user(self, mock_redis):
        """Test resetting attempts for user with no attempts"""
        auth = AuthSecurity(mock_redis)
        user_id = 99999

        # Should not crash
        await auth.reset_password_attempts(user_id)

        # Should have full attempts available
        remaining = await auth.get_remaining_attempts(user_id)
        assert remaining == MAX_ATTEMPTS

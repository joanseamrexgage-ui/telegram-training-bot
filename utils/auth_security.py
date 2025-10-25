"""
Authentication Security Utilities

BLOCKER-002 FIX: Redis-backed password attempt tracking
Prevents brute-force bypass via bot restart

Author: Production Readiness Team
Date: 2025-10-25
Version: 3.1
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple
from redis.asyncio import Redis

from utils.logger import logger

# Configuration
MAX_ATTEMPTS = 3
BLOCK_DURATION_MINUTES = 5
ATTEMPT_TTL_SECONDS = 300  # 5 minutes


class AuthSecurity:
    """Redis-backed authentication security"""

    def __init__(self, redis: Redis):
        """
        Initialize auth security manager

        Args:
            redis: Redis client instance
        """
        self.redis = redis

    async def increment_password_attempts(self, user_id: int) -> Tuple[int, Optional[datetime]]:
        """
        Increment password attempt counter for user

        Persists across bot restarts via Redis storage.
        Blocks user after MAX_ATTEMPTS failed attempts.

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (attempt_count, blocked_until_datetime)
            blocked_until is None if not blocked
        """
        key = f"admin:password_attempts:{user_id}"

        try:
            # Increment attempts counter
            attempts = await self.redis.incr(key)

            # Set TTL on first attempt
            if attempts == 1:
                await self.redis.expire(key, ATTEMPT_TTL_SECONDS)

            logger.info(
                f"🔐 Password attempt {attempts}/{MAX_ATTEMPTS} for user {user_id}"
            )

            # Block after MAX_ATTEMPTS
            if attempts >= MAX_ATTEMPTS:
                block_key = f"admin:blocked:{user_id}"
                blocked_until = datetime.utcnow() + timedelta(minutes=BLOCK_DURATION_MINUTES)

                # Store block timestamp
                await self.redis.set(
                    block_key,
                    blocked_until.isoformat(),
                    ex=BLOCK_DURATION_MINUTES * 60
                )

                logger.warning(
                    f"⚠️ User {user_id} BLOCKED until {blocked_until} "
                    f"(exceeded {MAX_ATTEMPTS} password attempts)"
                )

                return attempts, blocked_until

            return attempts, None

        except Exception as e:
            logger.error(f"❌ Error incrementing password attempts: {e}")
            # Fail open: return 0 attempts if Redis unavailable
            return 0, None

    async def is_user_blocked(self, user_id: int) -> Tuple[bool, Optional[datetime]]:
        """
        Check if user is blocked from authentication attempts

        Args:
            user_id: Telegram user ID

        Returns:
            Tuple of (is_blocked, blocked_until_datetime)
        """
        block_key = f"admin:blocked:{user_id}"

        try:
            blocked_until_str = await self.redis.get(block_key)

            if not blocked_until_str:
                return False, None

            blocked_until = datetime.fromisoformat(blocked_until_str)

            # Check if block has expired
            if datetime.utcnow() >= blocked_until:
                # Clean up expired block
                await self.redis.delete(block_key)
                await self.reset_password_attempts(user_id)
                return False, None

            return True, blocked_until

        except Exception as e:
            logger.error(f"❌ Error checking user block status: {e}")
            # Fail open: allow access if Redis unavailable
            return False, None

    async def reset_password_attempts(self, user_id: int) -> None:
        """
        Reset password attempt counter (called after successful login)

        Args:
            user_id: Telegram user ID
        """
        attempt_key = f"admin:password_attempts:{user_id}"
        block_key = f"admin:blocked:{user_id}"

        try:
            # Delete both attempt counter and block record
            await self.redis.delete(attempt_key, block_key)

            logger.info(f"✅ Password attempts reset for user {user_id}")

        except Exception as e:
            logger.error(f"❌ Error resetting password attempts: {e}")

    async def get_remaining_attempts(self, user_id: int) -> int:
        """
        Get number of remaining password attempts

        Args:
            user_id: Telegram user ID

        Returns:
            Number of attempts remaining (0 if blocked)
        """
        # Check if blocked
        is_blocked, _ = await self.is_user_blocked(user_id)
        if is_blocked:
            return 0

        # Get current attempts
        key = f"admin:password_attempts:{user_id}"
        try:
            attempts = await self.redis.get(key)
            current_attempts = int(attempts) if attempts else 0
            remaining = max(0, MAX_ATTEMPTS - current_attempts)
            return remaining
        except Exception as e:
            logger.error(f"❌ Error getting remaining attempts: {e}")
            return MAX_ATTEMPTS  # Fail open

    async def get_block_time_remaining(self, user_id: int) -> Optional[int]:
        """
        Get seconds remaining in block period

        Args:
            user_id: Telegram user ID

        Returns:
            Seconds remaining, or None if not blocked
        """
        is_blocked, blocked_until = await self.is_user_blocked(user_id)

        if not is_blocked or not blocked_until:
            return None

        remaining = (blocked_until - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))


# Global instance (initialized in bot.py)
_auth_security: Optional[AuthSecurity] = None


def init_auth_security(redis: Redis) -> AuthSecurity:
    """
    Initialize global auth security instance

    Args:
        redis: Redis client

    Returns:
        AuthSecurity instance
    """
    global _auth_security
    _auth_security = AuthSecurity(redis)
    logger.info("✅ AuthSecurity initialized with Redis backend")
    return _auth_security


def get_auth_security() -> Optional[AuthSecurity]:
    """Get global auth security instance"""
    return _auth_security


__all__ = [
    "AuthSecurity",
    "init_auth_security",
    "get_auth_security",
    "MAX_ATTEMPTS",
    "BLOCK_DURATION_MINUTES"
]

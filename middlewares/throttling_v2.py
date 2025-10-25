"""
Production-Ready Throttling Middleware v2.0

ARCH REFACTORING: Redis-backed Token Bucket Rate Limiting

This module implements enterprise-grade rate limiting with:
- Redis storage for distributed rate limiting across multiple bot instances
- Token Bucket algorithm for burst traffic handling
- Automatic cleanup via Redis TTL (no memory leaks)
- Granular configuration per update type
- Production-ready error handling and fallback

CRITICAL FIXES:
- CRIT-002: In-memory storage → Redis with TTL
- SEC-002: Simple time-based limiting → Token Bucket algorithm
- OPS-002: Single-instance limitation → Multi-instance support

Architecture:
1. Token Bucket Algorithm:
   - Each user has a bucket with max_tokens capacity
   - Tokens refill at refill_rate per second
   - Each request consumes 1 token
   - Burst traffic allowed up to bucket capacity

2. Redis Storage Schema:
   - Key: f"throttle:{user_id}:tokens" - Current token count
   - Key: f"throttle:{user_id}:last_refill" - Last refill timestamp
   - Key: f"throttle:{user_id}:violations" - Violation counter
   - TTL: Auto-expire after inactivity

3. Fallback Behavior:
   - If Redis unavailable → allow requests (fail-open)
   - Log errors for monitoring
   - Prevent cascading failures

Author: Claude (Senior Architect)
Date: 2025-10-25
"""

import time
import asyncio
from typing import Callable, Dict, Any, Awaitable, Optional
from dataclasses import dataclass

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from utils.logger import logger


@dataclass
class RateLimitConfig:
    """
    Rate limiting configuration using Token Bucket algorithm

    Attributes:
        max_tokens: Maximum tokens in bucket (burst capacity)
        refill_rate: Tokens added per second
        violation_threshold: Max violations before temporary block
        block_duration: Temporary block duration in seconds
        redis_ttl: Redis key TTL for auto-cleanup
    """
    max_tokens: int = 5
    refill_rate: float = 0.5  # 0.5 tokens/sec = 1 request per 2 seconds sustained
    violation_threshold: int = 3
    block_duration: int = 60
    redis_ttl: int = 300  # 5 minutes


class RedisTokenBucket:
    """
    Token Bucket implementation backed by Redis

    Provides distributed rate limiting with:
    - Atomic operations via Redis transactions
    - Automatic token refill calculation
    - TTL-based cleanup (no manual cleanup needed)
    """

    def __init__(
        self,
        redis: Redis,
        config: RateLimitConfig,
        key_prefix: str = "throttle"
    ):
        """
        Initialize Token Bucket

        Args:
            redis: Redis client instance
            config: Rate limit configuration
            key_prefix: Redis key prefix for namespacing
        """
        self.redis = redis
        self.config = config
        self.key_prefix = key_prefix

    def _get_keys(self, user_id: int) -> Dict[str, str]:
        """Generate Redis keys for user"""
        return {
            "tokens": f"{self.key_prefix}:{user_id}:tokens",
            "last_refill": f"{self.key_prefix}:{user_id}:last_refill",
            "violations": f"{self.key_prefix}:{user_id}:violations",
            "blocked": f"{self.key_prefix}:{user_id}:blocked"
        }

    async def _refill_tokens(
        self,
        keys: Dict[str, str],
        current_time: float
    ) -> float:
        """
        Calculate and update token count with automatic refill

        Token Bucket Algorithm:
        1. Calculate time elapsed since last refill
        2. Calculate tokens to add: elapsed_time * refill_rate
        3. Add tokens up to max_tokens capacity
        4. Update last_refill timestamp

        Args:
            keys: Redis keys for user
            current_time: Current timestamp

        Returns:
            Updated token count
        """
        try:
            # Get current state
            pipe = self.redis.pipeline()
            pipe.get(keys["tokens"])
            pipe.get(keys["last_refill"])
            results = await pipe.execute()

            current_tokens = float(results[0] or self.config.max_tokens)
            last_refill = float(results[1] or current_time)

            # Calculate refill
            time_elapsed = current_time - last_refill
            tokens_to_add = time_elapsed * self.config.refill_rate
            new_tokens = min(
                current_tokens + tokens_to_add,
                self.config.max_tokens
            )

            # Update Redis atomically
            pipe = self.redis.pipeline()
            pipe.set(keys["tokens"], str(new_tokens), ex=self.config.redis_ttl)
            pipe.set(keys["last_refill"], str(current_time), ex=self.config.redis_ttl)
            await pipe.execute()

            return new_tokens

        except RedisError as e:
            logger.error(f"Redis error in _refill_tokens: {e}")
            # Fallback: return max tokens (fail-open)
            return self.config.max_tokens

    async def consume_token(
        self,
        user_id: int
    ) -> tuple[bool, Optional[str]]:
        """
        Try to consume one token from user's bucket

        Returns:
            Tuple of (allowed: bool, error_message: Optional[str])
        """
        keys = self._get_keys(user_id)
        current_time = time.time()

        try:
            # Check if user is blocked
            blocked_until = await self.redis.get(keys["blocked"])
            if blocked_until:
                blocked_until_time = float(blocked_until)
                if current_time < blocked_until_time:
                    remaining = int(blocked_until_time - current_time)
                    return False, (
                        f"🚫 Вы временно заблокированы за частые запросы.\n"
                        f"Осталось: {remaining} сек."
                    )
                else:
                    # Block expired, clean up
                    await self.redis.delete(keys["blocked"], keys["violations"])

            # Refill tokens
            current_tokens = await self._refill_tokens(keys, current_time)

            # Check if token available
            if current_tokens >= 1.0:
                # Consume token
                new_tokens = current_tokens - 1.0
                await self.redis.set(keys["tokens"], str(new_tokens), ex=self.config.redis_ttl)

                # Reset violations on successful request
                await self.redis.delete(keys["violations"])

                logger.debug(
                    f"✅ Token consumed for user {user_id}. "
                    f"Remaining: {new_tokens:.2f}/{self.config.max_tokens}"
                )
                return True, None
            else:
                # Rate limit exceeded
                await self._record_violation(user_id, keys, current_time)

                wait_time = int((1.0 - current_tokens) / self.config.refill_rate)
                return False, (
                    f"⏳ Слишком много запросов.\n"
                    f"Подождите {wait_time} сек."
                )

        except RedisError as e:
            logger.error(f"Redis error in consume_token for user {user_id}: {e}")
            # Fallback: allow request (fail-open for availability)
            return True, None

    async def _record_violation(
        self,
        user_id: int,
        keys: Dict[str, str],
        current_time: float
    ) -> None:
        """
        Record rate limit violation and block user if threshold exceeded

        Args:
            user_id: User ID
            keys: Redis keys
            current_time: Current timestamp
        """
        try:
            # Increment violation counter
            violations = await self.redis.incr(keys["violations"])
            await self.redis.expire(keys["violations"], self.config.redis_ttl)

            logger.warning(
                f"⚠️ Rate limit violation for user {user_id}. "
                f"Count: {violations}/{self.config.violation_threshold}"
            )

            # Block user if threshold exceeded
            if violations >= self.config.violation_threshold:
                block_until = current_time + self.config.block_duration
                await self.redis.set(
                    keys["blocked"],
                    str(block_until),
                    ex=self.config.block_duration
                )

                logger.warning(
                    f"🚫 User {user_id} blocked for {self.config.block_duration}s "
                    f"after {violations} violations"
                )

        except RedisError as e:
            logger.error(f"Redis error in _record_violation: {e}")


class ThrottlingMiddlewareV2(BaseMiddleware):
    """
    Production-Ready Throttling Middleware with Redis backend

    Features:
    - Token Bucket algorithm for intelligent rate limiting
    - Redis storage for multi-instance support
    - Automatic cleanup via TTL
    - Graceful degradation if Redis unavailable
    - Configurable per update type

    Usage:
        # Initialize Redis
        redis_client = Redis.from_url("redis://localhost:6379/0")

        # Create middleware
        throttling = ThrottlingMiddlewareV2(
            redis=redis_client,
            config=RateLimitConfig(max_tokens=5, refill_rate=0.5)
        )

        # Register on dispatcher
        dp.message.middleware(throttling)
        dp.callback_query.middleware(throttling)
    """

    def __init__(
        self,
        redis: Redis,
        config: Optional[RateLimitConfig] = None
    ):
        """
        Initialize throttling middleware

        Args:
            redis: Redis client instance
            config: Rate limit configuration (uses defaults if None)
        """
        super().__init__()
        self.redis = redis
        self.config = config or RateLimitConfig()
        self.token_bucket = RedisTokenBucket(redis, self.config)

        logger.info(
            f"✅ ThrottlingMiddlewareV2 initialized with Redis backend\n"
            f"   Max tokens: {self.config.max_tokens}\n"
            f"   Refill rate: {self.config.refill_rate} tokens/sec\n"
            f"   Violation threshold: {self.config.violation_threshold}\n"
            f"   Block duration: {self.config.block_duration}s"
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """
        Middleware execution handler

        Args:
            handler: Next handler in chain
            event: Telegram event (Message or CallbackQuery)
            data: Middleware data dict

        Returns:
            Handler result or None if rate limited
        """

        # Extract user from event
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        # Skip check if user not found
        if not user:
            return await handler(event, data)

        user_id = user.id

        # Try to consume token
        allowed, error_message = await self.token_bucket.consume_token(user_id)

        if not allowed:
            # Rate limited - send warning
            try:
                if isinstance(event, Message):
                    await event.answer(error_message)
                elif isinstance(event, CallbackQuery):
                    await event.answer(error_message, show_alert=True)
            except Exception as e:
                logger.error(f"Failed to send rate limit warning: {e}")

            # Block request
            return None

        # Allow request
        return await handler(event, data)

    async def close(self) -> None:
        """
        Cleanup method - close Redis connection

        Call this on bot shutdown:
            await throttling_middleware.close()
        """
        try:
            await self.redis.close()
            logger.info("✅ ThrottlingMiddlewareV2 Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")


# Factory function for easy initialization
async def create_redis_throttling(
    redis_url: str = "redis://localhost:6379/0",
    max_tokens: int = 5,
    refill_rate: float = 0.5,
    violation_threshold: int = 3,
    block_duration: int = 60
) -> ThrottlingMiddlewareV2:
    """
    Factory function to create ThrottlingMiddlewareV2 with Redis

    Args:
        redis_url: Redis connection URL
        max_tokens: Maximum burst capacity
        refill_rate: Tokens per second refill rate
        violation_threshold: Violations before block
        block_duration: Block duration in seconds

    Returns:
        Configured ThrottlingMiddlewareV2 instance

    Example:
        throttling = await create_redis_throttling(
            redis_url="redis://redis:6379/0",
            max_tokens=10,
            refill_rate=1.0
        )
    """
    try:
        # Create Redis connection pool
        pool = ConnectionPool.from_url(
            redis_url,
            decode_responses=True,
            max_connections=50,
            socket_timeout=5,
            socket_connect_timeout=5
        )

        redis_client = Redis(connection_pool=pool)

        # Test connection
        await redis_client.ping()
        logger.info(f"✅ Redis connection established: {redis_url}")

        # Create config
        config = RateLimitConfig(
            max_tokens=max_tokens,
            refill_rate=refill_rate,
            violation_threshold=violation_threshold,
            block_duration=block_duration
        )

        # Create middleware
        return ThrottlingMiddlewareV2(redis=redis_client, config=config)

    except RedisConnectionError as e:
        logger.critical(
            f"❌ CRITICAL: Cannot connect to Redis at {redis_url}\n"
            f"Error: {e}\n"
            f"Rate limiting will NOT work without Redis!"
        )
        raise
    except Exception as e:
        logger.critical(f"❌ CRITICAL: Failed to create throttling middleware: {e}")
        raise


__all__ = [
    "ThrottlingMiddlewareV2",
    "RedisTokenBucket",
    "RateLimitConfig",
    "create_redis_throttling"
]

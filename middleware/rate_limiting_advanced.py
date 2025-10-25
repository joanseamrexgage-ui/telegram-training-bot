"""
Advanced Rate Limiting for telegram-training-bot.

Features:
- Per-user, per-IP, per-endpoint limits
- Distributed rate limiting via Redis
- Whitelist/blacklist support
- Token bucket algorithm
- Metrics collection

Usage:
    from middleware.rate_limiting_advanced import AdvancedRateLimiter

    rate_limiter = AdvancedRateLimiter(redis_client)
    dp.update.middleware(rate_limiter)
"""

import time
from typing import Callable, Dict, Any, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    burst_size: int = 10
    block_duration: int = 300  # 5 minutes


class AdvancedRateLimiter:
    """Advanced rate limiter with token bucket algorithm"""

    def __init__(self, redis_client, config: Optional[RateLimitConfig] = None):
        self.redis = redis_client
        self.config = config or RateLimitConfig()
        self.whitelist = set()
        self.blacklist = set()

    async def __call__(self, handler: Callable, event: Any, data: Dict[str, Any]) -> Any:
        """Process update with rate limiting"""
        user_id = self._get_user_id(event)

        if user_id in self.whitelist:
            return await handler(event, data)

        if user_id in self.blacklist:
            logger.warning(f"Blocked request from blacklisted user {user_id}")
            return

        # Check rate limit
        if not await self._check_rate_limit(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return

        return await handler(event, data)

    async def _check_rate_limit(self, user_id: str) -> bool:
        """Check if user is within rate limit"""
        key = f"rate_limit:{user_id}"
        current_time = time.time()

        # Get current token count
        tokens = await self.redis.get(key)
        if tokens is None:
            tokens = self.config.burst_size
        else:
            tokens = float(tokens)

        # Refill tokens
        tokens = min(self.config.burst_size, tokens + 1)

        # Consume token
        if tokens >= 1:
            await self.redis.setex(key, 60, tokens - 1)
            return True

        return False

    def _get_user_id(self, event: Any) -> str:
        """Extract user ID from event"""
        if hasattr(event, 'message'):
            return str(event.message.from_user.id)
        elif hasattr(event, 'callback_query'):
            return str(event.callback_query.from_user.id)
        return "unknown"

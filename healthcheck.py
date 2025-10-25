#!/usr/bin/env python3
"""
Production-Ready Health Check Script v2.0

OPS-001 FIX: Comprehensive health monitoring

This script is used by Docker's HEALTHCHECK and monitoring systems
to verify all critical services are operational.

Returns exit code 0 if healthy, non-zero if unhealthy.

Usage in Dockerfile:
    HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
        CMD python healthcheck.py

Checks:
1. Environment Configuration - Critical env vars present
2. Database Connection - PostgreSQL/SQLite responsive
3. Redis Connection - FSM and throttling Redis available
4. Telegram API - Bot token valid and API reachable
5. File System - Required files and directories accessible

Author: Claude (Senior Architect)
Date: 2025-10-25
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def check_env_vars() -> Tuple[bool, str]:
    """
    Check if critical environment variables are set

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        critical_vars = ["BOT_TOKEN", "DATABASE_URL", "REDIS_URL"]
        missing = []

        for var in critical_vars:
            if not os.getenv(var):
                missing.append(var)

        if missing:
            return False, f"Missing env vars: {', '.join(missing)}"

        return True, "All critical env vars present"
    except Exception as e:
        return False, f"Env check error: {e}"


async def check_database() -> Tuple[bool, str]:
    """
    Check database connection and basic query

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from database.database import check_db_health

        health = await check_db_health()

        if health.get("status") == "ok":
            users_count = health.get("stats", {}).get("users_count", 0)
            return True, f"DB OK (users: {users_count})"
        else:
            return False, f"DB unhealthy: {health.get('message', 'unknown')}"
    except Exception as e:
        return False, f"DB check failed: {e}"


async def check_redis() -> Tuple[bool, str]:
    """
    Check Redis connection for both FSM and throttling

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from redis.asyncio import Redis

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")

        # Test FSM Redis (db 0)
        redis_fsm = Redis.from_url(f"{redis_url}/0", decode_responses=True)
        await asyncio.wait_for(redis_fsm.ping(), timeout=2.0)
        await redis_fsm.close()

        # Test Throttling Redis (db 1)
        redis_throttle = Redis.from_url(f"{redis_url}/1", decode_responses=True)
        await asyncio.wait_for(redis_throttle.ping(), timeout=2.0)
        await redis_throttle.close()

        return True, "Redis OK (FSM + throttling)"
    except asyncio.TimeoutError:
        return False, "Redis timeout"
    except ConnectionError as e:
        return False, f"Redis connection failed: {e}"
    except Exception as e:
        return False, f"Redis check failed: {e}"


async def check_telegram_api() -> Tuple[bool, str]:
    """
    Check Telegram Bot API accessibility

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        from aiogram import Bot
        from aiogram.client.default import DefaultBotProperties

        token = os.getenv("BOT_TOKEN")
        if not token:
            return False, "No BOT_TOKEN"

        bot = Bot(token=token, default=DefaultBotProperties())

        # Test API with getMe
        me = await asyncio.wait_for(bot.get_me(), timeout=5.0)
        await bot.session.close()

        return True, f"Telegram API OK (@{me.username})"
    except asyncio.TimeoutError:
        return False, "Telegram API timeout"
    except Exception as e:
        return False, f"Telegram API failed: {str(e)[:50]}"


async def check_filesystem() -> Tuple[bool, str]:
    """
    Check required files and directories exist

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        required_files = [
            Path(__file__).parent / "bot.py",
            Path(__file__).parent / "config.py",
        ]

        required_dirs = [
            Path(__file__).parent / "handlers",
            Path(__file__).parent / "middlewares",
        ]

        for file_path in required_files:
            if not file_path.exists():
                return False, f"Missing file: {file_path.name}"

        for dir_path in required_dirs:
            if not dir_path.exists() or not dir_path.is_dir():
                return False, f"Missing directory: {dir_path.name}"

        return True, "Filesystem OK"
    except Exception as e:
        return False, f"Filesystem check failed: {e}"


async def main():
    """
    Run all health checks

    Exit codes:
    - 0: All checks passed (healthy)
    - 1: One or more critical checks failed (unhealthy)
    """
    print("=" * 60)
    print("PRODUCTION HEALTH CHECK v2.0")
    print("=" * 60)

    # Define checks (order matters for dependencies)
    checks = {
        "Environment": check_env_vars(),
        "Filesystem": check_filesystem(),
        "Database": check_database(),
        "Redis": check_redis(),
        "Telegram API": check_telegram_api(),
    }

    # Run checks concurrently (timeout 8s total)
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                *[check() for check in checks.values()],
                return_exceptions=True
            ),
            timeout=8.0
        )
    except asyncio.TimeoutError:
        print("❌ HEALTH CHECK TIMEOUT (>8s)", file=sys.stderr)
        sys.exit(1)

    # Process results
    check_results = {}
    for (check_name, _), result in zip(checks.items(), results):
        if isinstance(result, Exception):
            check_results[check_name] = (False, str(result))
        else:
            check_results[check_name] = result

    # Print results
    print()
    all_healthy = True
    for check_name, (success, message) in check_results.items():
        status = "✓" if success else "✗"
        color = "\033[92m" if success else "\033[91m"
        reset = "\033[0m"

        print(f"{color}{status}{reset} {check_name:15s} {message}")

        if not success:
            all_healthy = False

    print("=" * 60)

    # Final result
    if all_healthy:
        print("✅ HEALTH CHECK: PASSED")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ HEALTH CHECK: FAILED", file=sys.stderr)
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Health check interrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}", file=sys.stderr)
        sys.exit(1)

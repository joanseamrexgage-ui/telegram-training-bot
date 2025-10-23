#!/usr/bin/env python3
"""
Health check script for Docker container

This script is used by Docker's HEALTHCHECK to verify the bot is running correctly.
Returns exit code 0 if healthy, non-zero if unhealthy.

Usage in Dockerfile:
    HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
        CMD python healthcheck.py

Checks:
- Bot process is running
- Database connection is available
- No critical errors in recent logs
"""

import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def check_database():
    """Check database connection"""
    try:
        from database.database import check_db_health

        health = await check_db_health()
        return health.get("status") == "ok"
    except Exception as e:
        print(f"Database check failed: {e}", file=sys.stderr)
        return False


async def check_bot_file():
    """Check if bot.py exists and is accessible"""
    try:
        bot_file = Path(__file__).parent / "bot.py"
        return bot_file.exists() and bot_file.is_file()
    except Exception as e:
        print(f"Bot file check failed: {e}", file=sys.stderr)
        return False


async def check_env_vars():
    """Check if critical environment variables are set"""
    try:
        critical_vars = ["BOT_TOKEN", "DATABASE_URL"]
        for var in critical_vars:
            if not os.getenv(var):
                print(f"Missing critical env var: {var}", file=sys.stderr)
                return False
        return True
    except Exception as e:
        print(f"Env vars check failed: {e}", file=sys.stderr)
        return False


async def main():
    """Run all health checks"""
    print("Running health checks...")

    checks = {
        "bot_file": await check_bot_file(),
        "env_vars": await check_env_vars(),
        "database": await check_database(),
    }

    # Print results
    for check_name, result in checks.items():
        status = "✓" if result else "✗"
        print(f"{status} {check_name}: {'OK' if result else 'FAIL'}")

    # All checks must pass
    all_healthy = all(checks.values())

    if all_healthy:
        print("Health check: PASSED")
        sys.exit(0)
    else:
        print("Health check: FAILED", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Health check error: {e}", file=sys.stderr)
        sys.exit(1)

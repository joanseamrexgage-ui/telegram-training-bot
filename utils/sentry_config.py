"""
Sentry integration for production error tracking and monitoring

This module configures Sentry for:
- Automatic error tracking
- Performance monitoring
- Release tracking
- User context
"""

import os
import sentry_sdk
from sentry_sdk.integrations.asyncio import AsyncioIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import logging

from utils.logger import logger


def init_sentry(
    enable_performance: bool = True,
    enable_profiling: bool = False,
    traces_sample_rate: float = 0.1,
    profiles_sample_rate: float = 0.1,
) -> None:
    """
    Initialize Sentry SDK for error tracking and monitoring

    Args:
        enable_performance: Enable performance monitoring
        enable_profiling: Enable profiling (resource intensive)
        traces_sample_rate: Percentage of transactions to trace (0.0-1.0)
        profiles_sample_rate: Percentage of transactions to profile (0.0-1.0)

    Environment Variables Required:
        SENTRY_DSN: Sentry Data Source Name (project URL)
        SENTRY_ENVIRONMENT: Environment name (production, staging, development)
        SENTRY_RELEASE: Release version (optional, auto-detected from git)
    """

    sentry_dsn = os.getenv("SENTRY_DSN")

    # Skip initialization if no DSN provided
    if not sentry_dsn:
        logger.warning(
            "Sentry DSN not configured. Error tracking disabled. "
            "Set SENTRY_DSN environment variable to enable."
        )
        return

    # Get environment and release info
    environment = os.getenv("SENTRY_ENVIRONMENT", "production")
    release = os.getenv("SENTRY_RELEASE", _get_git_revision())

    # Configure logging integration
    sentry_logging = LoggingIntegration(
        level=logging.INFO,  # Capture info and above as breadcrumbs
        event_level=logging.ERROR  # Send errors as events
    )

    # Initialize Sentry SDK
    try:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=environment,
            release=release,
            # Integrations
            integrations=[
                AsyncioIntegration(),
                SqlalchemyIntegration(),
                sentry_logging,
            ],
            # Performance monitoring
            enable_tracing=enable_performance,
            traces_sample_rate=traces_sample_rate if enable_performance else 0,
            # Profiling
            profiles_sample_rate=profiles_sample_rate if enable_profiling else 0,
            # Error handling
            attach_stacktrace=True,
            send_default_pii=False,  # Don't send personally identifiable information
            # Performance
            max_breadcrumbs=50,
            # Filtering
            before_send=before_send_filter,
            before_breadcrumb=before_breadcrumb_filter,
        )

        logger.info(
            f"✅ Sentry initialized successfully. "
            f"Environment: {environment}, Release: {release}"
        )

    except Exception as e:
        logger.error(f"❌ Failed to initialize Sentry: {e}")


def _get_git_revision() -> str:
    """
    Get current git revision for release tracking

    Returns:
        Git commit SHA or 'unknown' if not available
    """
    try:
        import subprocess
        revision = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'],
            stderr=subprocess.DEVNULL
        ).decode('utf-8').strip()
        return revision[:8]  # Short SHA
    except Exception:
        return "unknown"


def before_send_filter(event, hint):
    """
    Filter events before sending to Sentry

    Args:
        event: Sentry event dict
        hint: Additional context

    Returns:
        Modified event or None to drop
    """

    # Don't send events for specific exceptions
    if 'exc_info' in hint:
        exc_type, exc_value, tb = hint['exc_info']

        # Ignore specific exception types
        ignored_exceptions = [
            'KeyboardInterrupt',
            'SystemExit',
        ]

        if exc_type.__name__ in ignored_exceptions:
            return None

    # Add custom tags
    event.setdefault('tags', {})
    event['tags']['bot_type'] = 'telegram_training'

    return event


def before_breadcrumb_filter(crumb, hint):
    """
    Filter breadcrumbs before adding to event

    Args:
        crumb: Breadcrumb dict
        hint: Additional context

    Returns:
        Modified crumb or None to drop
    """

    # Don't log sensitive data in breadcrumbs
    if crumb.get('category') == 'query':
        # Remove SQL query parameters that might contain sensitive data
        if 'data' in crumb:
            crumb['data'] = {'query': '[REDACTED]'}

    return crumb


def capture_telegram_context(user_id: int, username: str = None, chat_id: int = None):
    """
    Add Telegram-specific context to Sentry scope

    Args:
        user_id: Telegram user ID
        username: Telegram username
        chat_id: Telegram chat ID
    """

    with sentry_sdk.configure_scope() as scope:
        scope.set_user({
            "id": str(user_id),
            "username": username or "unknown"
        })
        scope.set_tag("chat_id", str(chat_id) if chat_id else "private")


def capture_handler_context(handler_name: str, callback_data: str = None):
    """
    Add handler context to Sentry scope

    Args:
        handler_name: Name of the handler function
        callback_data: Callback query data if applicable
    """

    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("handler", handler_name)
        if callback_data:
            scope.set_tag("callback_data", callback_data)


def capture_exception_with_context(
    exception: Exception,
    user_id: int = None,
    handler_name: str = None,
    extra: dict = None
):
    """
    Capture exception with additional context

    Args:
        exception: Exception to capture
        user_id: Telegram user ID
        handler_name: Handler where exception occurred
        extra: Additional context data
    """

    with sentry_sdk.push_scope() as scope:
        if user_id:
            scope.set_user({"id": str(user_id)})
        if handler_name:
            scope.set_tag("handler", handler_name)
        if extra:
            scope.set_context("extra", extra)

        sentry_sdk.capture_exception(exception)


def monitor_performance(operation_name: str):
    """
    Context manager for monitoring operation performance

    Usage:
        with monitor_performance("database_query"):
            result = await database.query(...)

    Args:
        operation_name: Name of the operation being monitored
    """

    return sentry_sdk.start_transaction(
        op="task",
        name=operation_name,
        sampled=True
    )


__all__ = [
    "init_sentry",
    "capture_telegram_context",
    "capture_handler_context",
    "capture_exception_with_context",
    "monitor_performance",
]

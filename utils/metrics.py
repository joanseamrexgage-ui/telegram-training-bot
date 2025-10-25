"""
Production metrics collection using Prometheus.

Provides comprehensive observability for:
- Request metrics (rate, latency, errors)
- System metrics (CPU, memory, Redis connections)
- Business metrics (active users, FSM states, admin sessions)
- Security metrics (timeouts, errors, failed logins)

Usage:
    from utils.metrics import metrics

    # Record request
    metrics.record_request("handler_name", "success", latency=0.5)

    # Record error
    metrics.record_error("ValueError", "handler_name", severity="error")

    # Get Prometheus metrics
    metrics_text = metrics.get_metrics()
"""

import time
import os
from typing import Optional, Dict, Any

try:
    from prometheus_client import (
        Counter, Histogram, Gauge, Info,
        generate_latest, CONTENT_TYPE_LATEST
    )
    import psutil
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

from utils.logger import logger


if METRICS_AVAILABLE:
    # ==================== REQUEST METRICS ====================

    request_total = Counter(
        'bot_requests_total',
        'Total bot requests',
        ['handler', 'status', 'user_type']
    )

    request_latency = Histogram(
        'bot_request_latency_seconds',
        'Request processing latency in seconds',
        ['handler'],
        buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]
    )

    # ==================== BUSINESS METRICS ====================

    active_users_24h = Gauge(
        'bot_active_users_24h',
        'Active users in last 24 hours'
    )

    fsm_states_total = Gauge(
        'bot_fsm_states_total',
        'Total FSM states in Redis'
    )

    admin_sessions = Gauge(
        'bot_admin_sessions_active',
        'Active admin sessions'
    )

    # ==================== SYSTEM METRICS ====================

    memory_usage_bytes = Gauge(
        'bot_memory_usage_bytes',
        'Memory usage in bytes'
    )

    cpu_usage_percent = Gauge(
        'bot_cpu_usage_percent',
        'CPU usage percentage'
    )

    # ==================== REDIS METRICS ====================

    redis_connections_active = Gauge(
        'bot_redis_connections_active',
        'Active Redis connections'
    )

    redis_failovers_total = Counter(
        'bot_redis_failovers_total',
        'Total Redis Sentinel failovers'
    )

    redis_operation_latency = Histogram(
        'bot_redis_operation_latency_seconds',
        'Redis operation latency in seconds',
        ['operation'],
        buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5]
    )

    # ==================== ERROR METRICS ====================

    errors_total = Counter(
        'bot_errors_total',
        'Total errors by type',
        ['error_type', 'handler', 'severity']
    )

    # ==================== TIMEOUT METRICS ====================

    timeouts_total = Counter(
        'bot_timeouts_total',
        'Total handler timeouts',
        ['handler']
    )

    # ==================== SECURITY METRICS ====================

    failed_logins_total = Counter(
        'bot_failed_logins_total',
        'Total failed login attempts'
    )

    blocked_users = Gauge(
        'bot_blocked_users_total',
        'Total blocked users'
    )

    # ==================== BOT INFO ====================

    bot_info = Info('bot_info', 'Bot information and version')


class MetricsCollector:
    """Centralized metrics collection for production monitoring"""

    def __init__(self):
        """Initialize metrics collector"""
        self.start_time = time.time()
        self.enabled = METRICS_AVAILABLE

        if not self.enabled:
            logger.warning(
                "⚠️ Prometheus metrics disabled - "
                "install prometheus-client and psutil to enable"
            )
        else:
            # Set bot info
            bot_info.info({
                'version': '3.2',
                'environment': os.getenv('ENVIRONMENT', 'development'),
                'bot_name': 'telegram-training-bot'
            })
            logger.info("📊 Prometheus metrics collector initialized")

    def update_system_metrics(self) -> None:
        """Update system resource metrics (CPU, memory)"""
        if not self.enabled:
            return

        try:
            process = psutil.Process(os.getpid())

            # Memory usage
            memory_info = process.memory_info()
            memory_usage_bytes.set(memory_info.rss)

            # CPU usage
            cpu_percent = process.cpu_percent(interval=0.1)
            cpu_usage_percent.set(cpu_percent)

        except Exception as e:
            logger.error(f"Error updating system metrics: {e}")

    def record_request(
        self,
        handler_name: str,
        status: str,
        latency: float,
        user_type: str = "user"
    ) -> None:
        """
        Record request metrics.

        Args:
            handler_name: Name of the handler function
            status: Request status (success, error, timeout)
            latency: Request latency in seconds
            user_type: Type of user (user, admin)
        """
        if not self.enabled:
            return

        try:
            request_total.labels(
                handler=handler_name,
                status=status,
                user_type=user_type
            ).inc()

            request_latency.labels(handler=handler_name).observe(latency)

        except Exception as e:
            logger.error(f"Error recording request metrics: {e}")

    def record_error(
        self,
        error_type: str,
        handler: str,
        severity: str = "error"
    ) -> None:
        """
        Record error metrics.

        Args:
            error_type: Type/class of error
            handler: Handler where error occurred
            severity: Error severity (warning, error, critical)
        """
        if not self.enabled:
            return

        try:
            errors_total.labels(
                error_type=error_type,
                handler=handler,
                severity=severity
            ).inc()

        except Exception as e:
            logger.error(f"Error recording error metrics: {e}")

    def record_timeout(self, handler_name: str) -> None:
        """
        Record timeout event.

        Args:
            handler_name: Name of the handler that timed out
        """
        if not self.enabled:
            return

        try:
            timeouts_total.labels(handler=handler_name).inc()

        except Exception as e:
            logger.error(f"Error recording timeout metrics: {e}")

    def record_redis_operation(self, operation: str, latency: float) -> None:
        """
        Record Redis operation latency.

        Args:
            operation: Redis operation (get, set, incr, etc.)
            latency: Operation latency in seconds
        """
        if not self.enabled:
            return

        try:
            redis_operation_latency.labels(operation=operation).observe(latency)

        except Exception as e:
            logger.error(f"Error recording Redis metrics: {e}")

    def record_redis_failover(self) -> None:
        """Record Redis Sentinel failover event"""
        if not self.enabled:
            return

        try:
            redis_failovers_total.inc()
            logger.warning("📊 Redis failover recorded in metrics")

        except Exception as e:
            logger.error(f"Error recording failover metrics: {e}")

    def update_active_users(self, count: int) -> None:
        """
        Update active users metric.

        Args:
            count: Number of active users in last 24 hours
        """
        if not self.enabled:
            return

        try:
            active_users_24h.set(count)

        except Exception as e:
            logger.error(f"Error updating active users metric: {e}")

    def record_failed_login(self) -> None:
        """Record failed login attempt"""
        if not self.enabled:
            return

        try:
            failed_logins_total.inc()

        except Exception as e:
            logger.error(f"Error recording failed login: {e}")

    def get_metrics(self) -> str:
        """
        Get Prometheus metrics in text format.

        Returns:
            Metrics in Prometheus text format
        """
        if not self.enabled:
            return "# Metrics not available - prometheus-client not installed\n"

        try:
            # Update system metrics before returning
            self.update_system_metrics()

            return generate_latest().decode('utf-8')

        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return f"# Error generating metrics: {e}\n"

    def get_stats(self) -> Dict[str, Any]:
        """
        Get metrics statistics as dictionary.

        Returns:
            Dictionary with current metric values
        """
        return {
            "enabled": self.enabled,
            "uptime_seconds": time.time() - self.start_time,
            "metrics_available": METRICS_AVAILABLE
        }


# Global metrics collector instance
metrics = MetricsCollector()


# ==================== HELPER DECORATORS ====================

def track_latency(operation_name: str):
    """
    Decorator to track operation latency.

    Usage:
        @track_latency("database_query")
        async def query_users():
            ...
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                latency = time.time() - start_time
                metrics.record_request(operation_name, "success", latency)
                return result
            except Exception as e:
                latency = time.time() - start_time
                metrics.record_request(operation_name, "error", latency)
                metrics.record_error(type(e).__name__, operation_name)
                raise
        return wrapper
    return decorator

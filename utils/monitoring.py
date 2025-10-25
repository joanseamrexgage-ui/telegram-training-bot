"""
Production monitoring server for telegram-training-bot.

Provides:
- Prometheus metrics HTTP server
- Periodic business metrics updates
- Health check endpoint
- Real-time metrics collection
"""

import asyncio
import logging
from prometheus_client import start_http_server, generate_latest, REGISTRY
from prometheus_client import Counter, Gauge, Histogram, Summary
import psutil
import os
from typing import Optional
from datetime import datetime


# ==================== METRICS DEFINITIONS ====================

# Request metrics
request_counter = Counter(
    'bot_requests_total',
    'Total number of bot requests',
    ['handler', 'status']
)

error_counter = Counter(
    'bot_errors_total',
    'Total number of errors',
    ['error_type']
)

request_latency = Histogram(
    'bot_request_latency_seconds',
    'Request latency in seconds',
    ['handler'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

# Business metrics
active_users_24h = Gauge(
    'bot_active_users_24h',
    'Number of active users in the last 24 hours'
)

fsm_states_total = Gauge(
    'bot_fsm_states_total',
    'Total number of active FSM states'
)

admin_sessions_active = Gauge(
    'bot_admin_sessions_active',
    'Number of active admin sessions'
)

user_registrations = Counter(
    'bot_user_registrations_total',
    'Total number of user registrations'
)

users_by_department = Gauge(
    'bot_users_by_department',
    'Number of users by department',
    ['department']
)

# System metrics
memory_usage = Gauge(
    'bot_memory_usage_bytes',
    'Memory usage in bytes'
)

cpu_usage = Gauge(
    'bot_cpu_usage_percent',
    'CPU usage percentage'
)

# Redis metrics
redis_connections = Gauge(
    'bot_redis_connections_active',
    'Number of active Redis connections'
)

redis_failovers = Counter(
    'bot_redis_failovers_total',
    'Total number of Redis Sentinel failovers'
)

redis_operation_latency = Histogram(
    'bot_redis_operation_latency_seconds',
    'Redis operation latency',
    ['operation'],
    buckets=[0.0001, 0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1]
)

redis_memory_usage = Gauge(
    'bot_redis_memory_usage_bytes',
    'Redis memory usage in bytes'
)

# Security metrics
failed_logins = Counter(
    'bot_failed_logins_total',
    'Total number of failed login attempts'
)

blocked_users = Gauge(
    'bot_blocked_users_total',
    'Number of currently blocked users'
)

timeouts = Counter(
    'bot_timeouts_total',
    'Total number of handler timeouts',
    ['handler']
)

handler_timeouts = Counter(
    'bot_handler_timeouts_total',
    'Total number of handler timeouts by handler',
    ['handler']
)

# Database metrics
database_queries = Counter(
    'bot_database_queries_total',
    'Total number of database queries',
    ['query_type']
)

database_query_duration = Histogram(
    'bot_database_query_duration_seconds',
    'Database query duration',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

database_connections_active = Gauge(
    'bot_database_connections_active',
    'Number of active database connections'
)

database_connections_max = Gauge(
    'bot_database_connections_max',
    'Maximum number of database connections'
)

# Admin operations
admin_operations = Counter(
    'bot_admin_operations_total',
    'Total number of admin operations',
    ['operation_type']
)

# FSM state management
stale_sessions = Gauge(
    'bot_stale_sessions_total',
    'Number of stale sessions'
)


# ==================== MONITORING SERVER ====================

class MonitoringServer:
    """
    Production monitoring server.

    Manages Prometheus metrics export and periodic metrics updates.
    """

    def __init__(self, port: int = 8080, update_interval: int = 30):
        """
        Initialize monitoring server.

        Args:
            port: HTTP server port for metrics endpoint
            update_interval: Interval in seconds for metrics updates
        """
        self.port = port
        self.update_interval = update_interval
        self.running = False
        self.process = psutil.Process(os.getpid())
        self.logger = logging.getLogger(__name__)

    async def start(self):
        """Start monitoring server"""
        try:
            # Start Prometheus HTTP server
            start_http_server(self.port)
            self.running = True

            self.logger.info(f"📊 Monitoring server started on port {self.port}")
            self.logger.info(f"📈 Metrics endpoint: http://localhost:{self.port}/metrics")

            # Start metrics update task
            asyncio.create_task(self._update_metrics_loop())

        except Exception as e:
            self.logger.error(f"Failed to start monitoring server: {e}")
            raise

    async def stop(self):
        """Stop monitoring server"""
        self.running = False
        self.logger.info("Monitoring server stopped")

    async def _update_metrics_loop(self):
        """Periodically update metrics"""
        while self.running:
            try:
                await self._update_system_metrics()
                await self._update_business_metrics()

            except Exception as e:
                self.logger.error(f"Metrics update error: {e}")

            await asyncio.sleep(self.update_interval)

    async def _update_system_metrics(self):
        """Update system resource metrics"""
        try:
            # Memory usage
            mem_info = self.process.memory_info()
            memory_usage.set(mem_info.rss)

            # CPU usage
            cpu_percent = self.process.cpu_percent(interval=1)
            cpu_usage.set(cpu_percent)

        except Exception as e:
            self.logger.error(f"System metrics update error: {e}")

    async def _update_business_metrics(self):
        """Update business metrics from database"""
        try:
            # These would typically query the database
            # For now, we just ensure the metrics exist

            # Note: In production, these would be actual queries:
            # from database.crud import get_active_users_count, get_fsm_states_count
            # active_count = await get_active_users_count()
            # active_users_24h.set(active_count)

            pass

        except Exception as e:
            self.logger.error(f"Business metrics update error: {e}")


# ==================== HELPER FUNCTIONS ====================

def track_request(handler: str, status: str):
    """Track a request"""
    request_counter.labels(handler=handler, status=status).inc()


def track_error(error_type: str):
    """Track an error"""
    error_counter.labels(error_type=error_type).inc()


def track_latency(handler: str, duration: float):
    """Track request latency"""
    request_latency.labels(handler=handler).observe(duration)


def track_user_registration():
    """Track a new user registration"""
    user_registrations.inc()


def track_failed_login():
    """Track a failed login attempt"""
    failed_logins.inc()


def track_timeout(handler: str):
    """Track a handler timeout"""
    timeouts.labels(handler=handler).inc()
    handler_timeouts.labels(handler=handler).inc()


def track_admin_operation(operation_type: str):
    """Track an admin operation"""
    admin_operations.labels(operation_type=operation_type).inc()


def track_database_query(query_type: str, duration: float):
    """Track a database query"""
    database_queries.labels(query_type=query_type).inc()
    database_query_duration.labels(query_type=query_type).observe(duration)


def track_redis_operation(operation: str, duration: float):
    """Track a Redis operation"""
    redis_operation_latency.labels(operation=operation).observe(duration)


def update_redis_connections(count: int):
    """Update Redis connections count"""
    redis_connections.set(count)


def track_redis_failover():
    """Track a Redis failover event"""
    redis_failovers.inc()


def update_blocked_users(count: int):
    """Update blocked users count"""
    blocked_users.set(count)


def update_fsm_states(count: int):
    """Update active FSM states count"""
    fsm_states_total.set(count)


def update_admin_sessions(count: int):
    """Update active admin sessions count"""
    admin_sessions_active.set(count)


def update_users_by_department(department: str, count: int):
    """Update users count by department"""
    users_by_department.labels(department=department).set(count)


def update_database_connections(active: int, max_connections: int):
    """Update database connection pool metrics"""
    database_connections_active.set(active)
    database_connections_max.set(max_connections)


# ==================== HEALTH CHECK ====================

def get_health_status() -> dict:
    """
    Get health status for health check endpoint.

    Returns:
        dict: Health status information
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "metrics": {
            "memory_bytes": memory_usage._value.get() if hasattr(memory_usage, '_value') else 0,
            "cpu_percent": cpu_usage._value.get() if hasattr(cpu_usage, '_value') else 0,
        }
    }


# ==================== CONTEXT MANAGERS ====================

class MetricsTimer:
    """Context manager for timing operations"""

    def __init__(self, handler: str):
        self.handler = handler
        self.start_time = None

    def __enter__(self):
        self.start_time = asyncio.get_event_loop().time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = asyncio.get_event_loop().time() - self.start_time
            track_latency(self.handler, duration)

        if exc_type:
            track_error(exc_type.__name__)


async def async_metrics_timer(handler: str):
    """Async context manager for timing operations"""
    start_time = asyncio.get_event_loop().time()
    try:
        yield
    except Exception as e:
        track_error(type(e).__name__)
        raise
    finally:
        duration = asyncio.get_event_loop().time() - start_time
        track_latency(handler, duration)

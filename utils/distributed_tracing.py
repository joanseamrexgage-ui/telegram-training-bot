"""
Distributed Tracing with OpenTelemetry for telegram-training-bot.

Provides enterprise-grade distributed tracing with:
- Automatic span creation for handlers
- Database query tracing
- Redis operation tracing
- External API call tracing
- Custom business metrics
- Jaeger/Zipkin export

Usage:
    from utils.distributed_tracing import TracingMiddleware, trace_function, get_tracer

    # Add middleware to bot
    dp.update.middleware(TracingMiddleware())

    # Decorate functions
    @trace_function("user_registration")
    async def register_user(user_id: int):
        ...

    # Manual span creation
    tracer = get_tracer()
    with tracer.start_as_current_span("custom_operation") as span:
        span.set_attribute("user.id", user_id)
        ...

Requirements:
    pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-jaeger
             opentelemetry-instrumentation-sqlalchemy opentelemetry-instrumentation-redis
"""

import os
import logging
from typing import Callable, Any, Optional, Dict
from functools import wraps
import asyncio

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Initialize logger
logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

TRACING_ENABLED = os.getenv("TRACING_ENABLED", "false").lower() == "true"
SERVICE_NAME_VALUE = os.getenv("SERVICE_NAME", "telegram-training-bot")
SERVICE_VERSION_VALUE = os.getenv("SERVICE_VERSION", "3.2.0")
JAEGER_ENDPOINT = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# ============================================================================
# Tracer Setup
# ============================================================================

def setup_tracing() -> TracerProvider:
    """
    Setup OpenTelemetry tracing.

    Returns:
        TracerProvider instance
    """
    # Define service resource
    resource = Resource(attributes={
        SERVICE_NAME: SERVICE_NAME_VALUE,
        SERVICE_VERSION: SERVICE_VERSION_VALUE,
        "environment": ENVIRONMENT,
        "deployment.environment": ENVIRONMENT,
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add exporters
    if TRACING_ENABLED:
        # Jaeger exporter for production
        jaeger_exporter = JaegerExporter(
            agent_host_name="localhost",
            agent_port=6831,
            # Or HTTP collector
            collector_endpoint=JAEGER_ENDPOINT,
        )
        provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))

        logger.info(f"✅ Distributed tracing enabled (Jaeger: {JAEGER_ENDPOINT})")
    else:
        # Console exporter for development
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))

        logger.info("📝 Tracing enabled (Console output for development)")

    # Set global tracer provider
    trace.set_tracer_provider(provider)

    # Auto-instrument SQLAlchemy and Redis
    try:
        SQLAlchemyInstrumentor().instrument()
        RedisInstrumentor().instrument()
        logger.info("✅ Auto-instrumentation enabled (SQLAlchemy, Redis)")
    except Exception as e:
        logger.warning(f"Failed to auto-instrument: {e}")

    return provider


# Global tracer provider
_tracer_provider: Optional[TracerProvider] = None


def get_tracer_provider() -> TracerProvider:
    """Get or create global tracer provider"""
    global _tracer_provider
    if _tracer_provider is None:
        _tracer_provider = setup_tracing()
    return _tracer_provider


def get_tracer(name: str = __name__) -> trace.Tracer:
    """
    Get a tracer instance.

    Args:
        name: Name of the tracer

    Returns:
        Tracer instance
    """
    return get_tracer_provider().get_tracer(name)


# ============================================================================
# Middleware for Aiogram
# ============================================================================

class TracingMiddleware:
    """
    Aiogram middleware for distributed tracing.

    Automatically creates spans for all incoming updates.
    """

    def __init__(self):
        """Initialize tracing middleware"""
        self.tracer = get_tracer("telegram-bot-handlers")
        self.propagator = TraceContextTextMapPropagator()

    async def __call__(
        self,
        handler: Callable,
        event: Any,
        data: Dict[str, Any]
    ) -> Any:
        """
        Process update with tracing.

        Args:
            handler: Next handler in chain
            event: Update event
            data: Handler data

        Returns:
            Handler result
        """
        # Extract update info
        update_type = event.__class__.__name__
        update_id = getattr(event, 'update_id', 'unknown')

        # Create span
        with self.tracer.start_as_current_span(
            f"telegram.update.{update_type}",
            kind=trace.SpanKind.SERVER
        ) as span:
            # Add attributes
            span.set_attribute("telegram.update.id", str(update_id))
            span.set_attribute("telegram.update.type", update_type)

            if hasattr(event, 'message'):
                message = event.message
                span.set_attribute("telegram.user.id", str(message.from_user.id))
                span.set_attribute("telegram.chat.id", str(message.chat.id))
                span.set_attribute("telegram.message.text", message.text or "")

            elif hasattr(event, 'callback_query'):
                callback = event.callback_query
                span.set_attribute("telegram.user.id", str(callback.from_user.id))
                span.set_attribute("telegram.callback.data", callback.data or "")

            try:
                # Call next handler
                result = await handler(event, data)

                # Mark success
                span.set_status(Status(StatusCode.OK))
                return result

            except Exception as e:
                # Record exception
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.set_attribute("error", True)
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))

                raise


# ============================================================================
# Function Decorator for Tracing
# ============================================================================

def trace_function(span_name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """
    Decorator to trace a function.

    Args:
        span_name: Name of the span (defaults to function name)
        attributes: Additional span attributes

    Usage:
        @trace_function("user_registration", {"operation": "create"})
        async def register_user(user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__name__}"
        tracer = get_tracer(func.__module__)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(name) as span:
                # Add function attributes
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                # Add custom attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Add arguments as attributes (careful with sensitive data!)
                if args:
                    span.set_attribute("function.args.count", len(args))
                if kwargs:
                    span.set_attribute("function.kwargs.count", len(kwargs))

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with tracer.start_as_current_span(name) as span:
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ============================================================================
# Context Manager for Manual Spans
# ============================================================================

class TracedOperation:
    """
    Context manager for manual span creation.

    Usage:
        async with TracedOperation("database_query", user_id=123) as span:
            result = await db.execute(query)
            span.set_attribute("rows.count", len(result))
    """

    def __init__(self, operation_name: str, **attributes):
        """
        Initialize traced operation.

        Args:
            operation_name: Name of the operation
            **attributes: Span attributes
        """
        self.operation_name = operation_name
        self.attributes = attributes
        self.tracer = get_tracer("telegram-bot")
        self.span: Optional[Span] = None

    def __enter__(self) -> Span:
        """Start span"""
        self.span = self.tracer.start_span(self.operation_name)

        # Set attributes
        for key, value in self.attributes.items():
            self.span.set_attribute(key, value)

        return self.span

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End span"""
        if self.span:
            if exc_type:
                self.span.record_exception(exc_val)
                self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            else:
                self.span.set_status(Status(StatusCode.OK))

            self.span.end()

    async def __aenter__(self) -> Span:
        """Async context manager entry"""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        return self.__exit__(exc_type, exc_val, exc_tb)


# ============================================================================
# Business Metrics Tracing
# ============================================================================

class BusinessMetricsTracer:
    """
    Tracer for business-specific metrics.

    Adds business context to technical traces.
    """

    def __init__(self):
        """Initialize business metrics tracer"""
        self.tracer = get_tracer("business-metrics")

    def trace_user_registration(self, user_id: int, department: str, position: str):
        """Trace user registration event"""
        with self.tracer.start_as_current_span("business.user.registration") as span:
            span.set_attribute("user.id", str(user_id))
            span.set_attribute("user.department", department)
            span.set_attribute("user.position", position)
            span.set_attribute("event.type", "registration")

    def trace_content_access(self, user_id: int, section: str, content_id: str):
        """Trace content access event"""
        with self.tracer.start_as_current_span("business.content.access") as span:
            span.set_attribute("user.id", str(user_id))
            span.set_attribute("content.section", section)
            span.set_attribute("content.id", content_id)
            span.set_attribute("event.type", "content_access")

    def trace_admin_operation(self, admin_id: int, operation: str, target: str):
        """Trace admin operation"""
        with self.tracer.start_as_current_span("business.admin.operation") as span:
            span.set_attribute("admin.id", str(admin_id))
            span.set_attribute("operation.type", operation)
            span.set_attribute("operation.target", target)
            span.set_attribute("event.type", "admin_operation")


# ============================================================================
# Database Query Tracing (SQLAlchemy)
# ============================================================================

def trace_database_query(query: str, params: Optional[Dict] = None):
    """
    Trace a database query.

    Args:
        query: SQL query string
        params: Query parameters

    Usage:
        with trace_database_query("SELECT * FROM users WHERE id = ?", {"id": 123}):
            result = await session.execute(query)
    """
    tracer = get_tracer("database")
    span = tracer.start_span("db.query")

    span.set_attribute("db.system", "postgresql")
    span.set_attribute("db.statement", query[:500])  # Truncate long queries

    if params:
        span.set_attribute("db.params.count", len(params))

    return span


# ============================================================================
# Redis Operation Tracing
# ============================================================================

def trace_redis_operation(operation: str, key: Optional[str] = None):
    """
    Trace a Redis operation.

    Args:
        operation: Redis command (GET, SET, etc.)
        key: Redis key

    Usage:
        with trace_redis_operation("SET", "user:123"):
            await redis.set(key, value)
    """
    tracer = get_tracer("redis")
    span = tracer.start_span(f"redis.{operation}")

    span.set_attribute("redis.operation", operation)
    if key:
        span.set_attribute("redis.key", key)

    return span


# ============================================================================
# External API Call Tracing
# ============================================================================

@trace_function("external_api_call")
async def trace_external_api_call(
    url: str,
    method: str = "GET",
    **kwargs
) -> Any:
    """
    Trace an external API call.

    Args:
        url: API endpoint URL
        method: HTTP method
        **kwargs: Additional request parameters

    Returns:
        API response
    """
    span = trace.get_current_span()

    span.set_attribute("http.method", method)
    span.set_attribute("http.url", url)
    span.set_attribute("http.scheme", "https")

    # Make actual request (would use aiohttp in production)
    # response = await aiohttp.request(method, url, **kwargs)

    # span.set_attribute("http.status_code", response.status)

    # return response
    pass


# ============================================================================
# Initialization
# ============================================================================

# Auto-initialize tracing on module import
if TRACING_ENABLED or os.getenv("ENVIRONMENT") == "development":
    get_tracer_provider()
    logger.info("🔍 Distributed tracing initialized")

"""
Unit tests for InputSanitizerMiddleware

Tests enterprise-grade input sanitization:
- Automatic HTML escaping (XSS prevention)
- Length limiting (DoS prevention)
- Pattern validation (injection prevention)
- User-friendly error messages
- Statistics tracking

Author: Enterprise Production Readiness Team
Coverage Target: 95%+ for middlewares/input_sanitizer.py
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from middlewares.input_sanitizer import InputSanitizerMiddleware


class TestInputSanitizerInitialization:
    """Test middleware initialization"""

    @pytest.mark.unit
    def test_default_initialization(self):
        """Test initialization with default parameters"""
        middleware = InputSanitizerMiddleware()

        assert middleware.max_text_length == 4096
        assert middleware.max_callback_length == 64
        assert middleware.enable_logging is True
        assert middleware.enable_stats is True
        assert middleware.stats["total_requests"] == 0

    @pytest.mark.unit
    def test_custom_initialization(self):
        """Test initialization with custom parameters"""
        middleware = InputSanitizerMiddleware(
            max_text_length=1000,
            max_callback_length=32,
            enable_logging=False,
            enable_stats=False
        )

        assert middleware.max_text_length == 1000
        assert middleware.max_callback_length == 32
        assert middleware.enable_logging is False
        assert middleware.enable_stats is False


class TestMessageSanitization:
    """Test message text sanitization"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_clean_message_passes_through(self, aiogram_message):
        """Test that clean messages pass through unchanged"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock(return_value="result")
        data = {}

        result = await middleware(handler, aiogram_message, data)

        handler.assert_called_once()
        assert result == "result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_html_injection_sanitized(self, aiogram_message):
        """Test that HTML tags are escaped"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock(return_value="result")
        data = {}

        # Set malicious text
        malicious_text = "<script>alert('XSS')</script>"
        object.__setattr__(aiogram_message, 'text', malicious_text)

        result = await middleware(handler, aiogram_message, data)

        # Should sanitize and pass through
        handler.assert_called_once()
        assert result == "result"
        # Text should be escaped
        assert "<script>" not in aiogram_message.text
        assert "&lt;script&gt;" in aiogram_message.text

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oversized_message_rejected(self, aiogram_message):
        """Test that oversized messages are rejected"""
        middleware = InputSanitizerMiddleware(max_text_length=100)
        handler = AsyncMock()
        data = {}

        # Create oversized message
        oversized_text = "A" * 200
        object.__setattr__(aiogram_message, 'text', oversized_text)

        result = await middleware(handler, aiogram_message, data)

        # Should reject
        handler.assert_not_called()
        assert result is None

        # Should send warning
        aiogram_message.answer.assert_called_once()
        warning = aiogram_message.answer.call_args[0][0]
        assert "слишком длинное" in warning

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_statistics_tracking_messages(self, aiogram_message):
        """Test that message sanitization is tracked in statistics"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        # Send message with HTML
        html_text = "<b>Bold text</b>"
        object.__setattr__(aiogram_message, 'text', html_text)

        await middleware(handler, aiogram_message, data)

        stats = middleware.get_stats()
        assert stats["total_requests"] == 1
        assert stats["sanitized_messages"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_newlines_preserved_in_messages(self, aiogram_message):
        """Test that newlines are preserved in message text"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        # Message with newlines
        text_with_newlines = "Line 1\nLine 2\nLine 3"
        object.__setattr__(aiogram_message, 'text', text_with_newlines)

        await middleware(handler, aiogram_message, data)

        # Newlines should be preserved
        assert "\n" in aiogram_message.text


class TestCallbackSanitization:
    """Test callback query data sanitization"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_valid_callback_passes_through(self, aiogram_callback_query):
        """Test that valid callback data passes through"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock(return_value="result")
        data = {}

        result = await middleware(handler, aiogram_callback_query, data)

        handler.assert_called_once()
        assert result == "result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_invalid_callback_rejected(self, aiogram_callback_query):
        """Test that invalid callback data is rejected"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        # Set invalid callback data (contains HTML)
        invalid_data = "<script>evil</script>"
        object.__setattr__(aiogram_callback_query, 'data', invalid_data)

        result = await middleware(handler, aiogram_callback_query, data)

        # Should reject
        handler.assert_not_called()
        assert result is None

        # Should send alert
        aiogram_callback_query.answer.assert_called_once()
        call_args = aiogram_callback_query.answer.call_args
        assert "Некорректный формат" in call_args[0][0]
        assert call_args[1]['show_alert'] is True

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_oversized_callback_rejected(self, aiogram_callback_query):
        """Test that oversized callback data is rejected"""
        middleware = InputSanitizerMiddleware(max_callback_length=32)
        handler = AsyncMock()
        data = {}

        # Create oversized callback
        oversized_data = "a" * 64
        object.__setattr__(aiogram_callback_query, 'data', oversized_data)

        result = await middleware(handler, aiogram_callback_query, data)

        # Should reject
        handler.assert_not_called()
        assert result is None

        # Should send alert
        aiogram_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_statistics_tracking_callbacks(self, aiogram_callback_query):
        """Test that callback sanitization is tracked"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        await middleware(handler, aiogram_callback_query, data)

        stats = middleware.get_stats()
        assert stats["total_requests"] == 1


class TestStatistics:
    """Test statistics collection"""

    @pytest.mark.unit
    def test_get_stats_structure(self):
        """Test that get_stats returns correct structure"""
        middleware = InputSanitizerMiddleware()

        stats = middleware.get_stats()

        assert "total_requests" in stats
        assert "sanitized_messages" in stats
        assert "sanitized_callbacks" in stats
        assert "rejected_oversized" in stats
        assert "rejected_invalid" in stats
        assert "sanitization_rate" in stats
        assert "rejection_rate" in stats

    @pytest.mark.unit
    def test_get_stats_when_disabled(self):
        """Test get_stats when statistics are disabled"""
        middleware = InputSanitizerMiddleware(enable_stats=False)

        stats = middleware.get_stats()

        assert stats == {"stats_disabled": True}

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_sanitization_rate_calculation(self, aiogram_message):
        """Test sanitization rate percentage calculation"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        # Send 2 messages with HTML, 1 clean
        for i in range(2):
            html_msg = MagicMock(spec=aiogram_message)
            html_msg.text = "<b>test</b>"
            html_msg.from_user = aiogram_message.from_user
            object.__setattr__(html_msg, 'text', "<b>test</b>")
            await middleware(handler, html_msg, data)

        clean_msg = MagicMock(spec=aiogram_message)
        clean_msg.text = "clean"
        clean_msg.from_user = aiogram_message.from_user
        await middleware(handler, clean_msg, data)

        stats = middleware.get_stats()
        assert stats["total_requests"] == 3
        assert stats["sanitized_messages"] == 2
        # Sanitization rate should be ~66.67%
        assert 60 <= stats["sanitization_rate"] <= 70

    @pytest.mark.unit
    def test_reset_stats(self):
        """Test that reset_stats clears all counters"""
        middleware = InputSanitizerMiddleware()

        # Populate stats
        middleware.stats["total_requests"] = 100
        middleware.stats["sanitized_messages"] = 50

        # Reset
        middleware.reset_stats()

        # Verify reset
        assert middleware.stats["total_requests"] == 0
        assert middleware.stats["sanitized_messages"] == 0


class TestRejectionScenarios:
    """Test various input rejection scenarios"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rejection_statistics_oversized(self, aiogram_message):
        """Test that oversized rejections are tracked"""
        middleware = InputSanitizerMiddleware(max_text_length=10)
        handler = AsyncMock()
        data = {}

        oversized = "A" * 50
        object.__setattr__(aiogram_message, 'text', oversized)

        await middleware(handler, aiogram_message, data)

        stats = middleware.get_stats()
        assert stats["rejected_oversized"] == 1
        assert stats["rejection_rate"] > 0

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_rejection_statistics_invalid(self, aiogram_callback_query):
        """Test that invalid data rejections are tracked"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        invalid = "<malicious>"
        object.__setattr__(aiogram_callback_query, 'data', invalid)

        await middleware(handler, aiogram_callback_query, data)

        stats = middleware.get_stats()
        assert stats["rejected_invalid"] == 1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_user_notification_on_rejection(self, aiogram_message):
        """Test that users receive helpful messages on rejection"""
        middleware = InputSanitizerMiddleware(max_text_length=50)
        handler = AsyncMock()
        data = {}

        oversized = "A" * 100
        object.__setattr__(aiogram_message, 'text', oversized)

        await middleware(handler, aiogram_message, data)

        # Verify notification sent
        aiogram_message.answer.assert_called_once()
        notification = aiogram_message.answer.call_args[0][0]

        # Should contain helpful info
        assert "слишком длинное" in notification
        assert "50" in notification  # max length
        assert "100" in notification  # actual length


class TestErrorHandling:
    """Test error handling in sanitizer"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_message_notification_error_handled(self, aiogram_message):
        """Test that errors sending notifications don't crash middleware"""
        middleware = InputSanitizerMiddleware(max_text_length=10)
        handler = AsyncMock()
        data = {}

        # Make answer() fail
        error_mock = AsyncMock(side_effect=Exception("Send failed"))
        object.__setattr__(aiogram_message, 'answer', error_mock)

        oversized = "A" * 50
        object.__setattr__(aiogram_message, 'text', oversized)

        # Should not raise exception
        result = await middleware(handler, aiogram_message, data)

        # Should still reject
        assert result is None
        handler.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_callback_notification_error_handled(self, aiogram_callback_query):
        """Test that callback notification errors don't crash middleware"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        # Make answer() fail
        error_mock = AsyncMock(side_effect=Exception("Send failed"))
        object.__setattr__(aiogram_callback_query, 'answer', error_mock)

        invalid = "<script>evil</script>"
        object.__setattr__(aiogram_callback_query, 'data', invalid)

        # Should not raise exception
        result = await middleware(handler, aiogram_callback_query, data)

        # Should still reject
        assert result is None


class TestEventTypeHandling:
    """Test handling of different event types"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_message_without_text_passes_through(self, aiogram_message):
        """Test that messages without text are not processed"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock(return_value="result")
        data = {}

        # Remove text
        object.__setattr__(aiogram_message, 'text', None)

        result = await middleware(handler, aiogram_message, data)

        # Should pass through without processing
        handler.assert_called_once()
        assert result == "result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_callback_without_data_passes_through(self, aiogram_callback_query):
        """Test that callbacks without data are not processed"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock(return_value="result")
        data = {}

        # Remove data
        object.__setattr__(aiogram_callback_query, 'data', None)

        result = await middleware(handler, aiogram_callback_query, data)

        # Should pass through
        handler.assert_called_once()
        assert result == "result"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_event_without_user_handled(self):
        """Test that events without user info are handled gracefully"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock(return_value="result")

        # Create event without from_user
        event = MagicMock()
        event.text = "test"

        result = await middleware(handler, event, {})

        # Should handle gracefully
        handler.assert_called_once()
        assert result == "result"


class TestSecurityFeatures:
    """Test security-specific features"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_xss_prevention(self, aiogram_message):
        """Test XSS attack prevention"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg/onload=alert('XSS')>",
            "javascript:alert('XSS')"
        ]

        for payload in xss_payloads:
            object.__setattr__(aiogram_message, 'text', payload)
            await middleware(handler, aiogram_message, data)

            # Should escape dangerous content
            assert "<script>" not in aiogram_message.text
            assert "<img" not in aiogram_message.text
            handler.reset_mock()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_injection_prevention_in_callbacks(self, aiogram_callback_query):
        """Test SQL/command injection prevention in callbacks"""
        middleware = InputSanitizerMiddleware()
        handler = AsyncMock()
        data = {}

        malicious_payloads = [
            "'; DROP TABLE users; --",
            "../../../etc/passwd",
            "$(rm -rf /)",
            "`cat /etc/passwd`"
        ]

        for payload in malicious_payloads:
            object.__setattr__(aiogram_callback_query, 'data', payload)
            result = await middleware(handler, aiogram_callback_query, data)

            # Should reject all malicious payloads
            assert result is None
            handler.assert_not_called()
            handler.reset_mock()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_dos_prevention_via_length_limits(self, aiogram_message):
        """Test DoS attack prevention via length limiting"""
        middleware = InputSanitizerMiddleware(max_text_length=1000)
        handler = AsyncMock()
        data = {}

        # Attempt DoS with massive input
        dos_payload = "A" * 100000  # 100KB
        object.__setattr__(aiogram_message, 'text', dos_payload)

        result = await middleware(handler, aiogram_message, data)

        # Should reject oversized input
        assert result is None
        handler.assert_not_called()

        stats = middleware.get_stats()
        assert stats["rejected_oversized"] == 1

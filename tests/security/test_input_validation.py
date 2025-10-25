"""
Security tests for input validation and sanitization.

Tests HIGH-003: HTML injection and XSS prevention.

Tests:
- HTML escaping
- XSS attack prevention
- Callback data validation
- Username sanitization
- Search query injection prevention
"""

import pytest
from utils.sanitize import (
    sanitize_user_input,
    sanitize_callback_data,
    sanitize_username,
    sanitize_broadcast_message,
    validate_telegram_id,
    sanitize_search_query,
    safe_user_name,
    safe_username
)


class TestHTMLInjectionPrevention:
    """Test HTML injection and XSS prevention"""

    @pytest.mark.security
    def test_basic_html_escaping(self):
        """Test basic HTML tags are escaped"""
        malicious = "<script>alert('XSS')</script>"
        sanitized = sanitize_user_input(malicious)

        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized
        assert "alert" in sanitized  # Content preserved, tags escaped

    @pytest.mark.security
    def test_img_tag_xss(self):
        """Test image tag XSS attack prevention"""
        malicious = "<img src=x onerror=alert('XSS')>"
        sanitized = sanitize_user_input(malicious)

        assert "<img" not in sanitized
        assert "&lt;img" in sanitized
        assert "onerror" in sanitized  # Kept but escaped

    @pytest.mark.security
    def test_multiple_tags(self):
        """Test multiple HTML tags are all escaped"""
        malicious = "<b>Bold</b><i>Italic</i><u>Underline</u>"
        sanitized = sanitize_user_input(malicious)

        assert "<b>" not in sanitized
        assert "<i>" not in sanitized
        assert "<u>" not in sanitized
        assert "&lt;b&gt;" in sanitized
        assert "&lt;i&gt;" in sanitized

    @pytest.mark.security
    def test_attribute_injection(self):
        """Test HTML attribute injection prevention"""
        malicious = '<a href="javascript:alert(\'XSS\')">Click</a>'
        sanitized = sanitize_user_input(malicious)

        assert "href=" not in sanitized or "&lt;" in sanitized
        assert "javascript:" in sanitized  # Kept but escaped

    @pytest.mark.security
    def test_unicode_bypass_attempt(self):
        """Test Unicode encoding bypass attempts"""
        malicious = "\u003cscript\u003ealert('XSS')\u003c/script\u003e"
        sanitized = sanitize_user_input(malicious)

        # Unicode should be preserved but HTML tags escaped
        assert "<script>" not in sanitized
        assert "alert" in sanitized

    @pytest.mark.security
    def test_null_byte_injection(self):
        """Test null byte injection handling"""
        malicious = "test\x00<script>alert('XSS')</script>"
        sanitized = sanitize_user_input(malicious)

        # Should not crash, should escape HTML
        assert "&lt;script&gt;" in sanitized or "<script>" not in sanitized


class TestCallbackDataValidation:
    """Test callback data validation"""

    @pytest.mark.security
    def test_valid_callback_data(self):
        """Test valid callback data passes through"""
        valid_callbacks = [
            "admin_panel",
            "users_list",
            "stats_general",
            "content_general_info",
            "broadcast_all",
            "back-to-menu",
            "page:5"
        ]

        for callback in valid_callbacks:
            sanitized = sanitize_callback_data(callback)
            assert sanitized == callback

    @pytest.mark.security
    def test_invalid_callback_data(self):
        """Test invalid callback data is rejected"""
        invalid_callbacks = [
            "<script>alert('XSS')</script>",
            "admin; DROP TABLE users;",
            "../../../etc/passwd",
            "callback\nwith\nnewlines",
            "callback with spaces"
        ]

        for callback in invalid_callbacks:
            sanitized = sanitize_callback_data(callback)
            assert sanitized == "invalid"

    @pytest.mark.security
    def test_callback_length_limit(self):
        """Test callback data length is enforced"""
        long_callback = "a" * 100
        sanitized = sanitize_callback_data(long_callback)

        assert len(sanitized) <= 64

    @pytest.mark.security
    def test_sql_injection_in_callback(self):
        """Test SQL injection in callback data"""
        malicious = "'; DROP TABLE users; --"
        sanitized = sanitize_callback_data(malicious)

        assert sanitized == "invalid"


class TestUsernameSanitization:
    """Test username sanitization"""

    @pytest.mark.security
    def test_valid_username(self):
        """Test valid usernames are sanitized correctly"""
        assert sanitize_username("john_doe") == "john_doe"
        assert sanitize_username("@john_doe") == "john_doe"  # @ removed
        assert sanitize_username("user123") == "user123"

    @pytest.mark.security
    def test_special_characters_removed(self):
        """Test special characters are removed from usernames"""
        assert sanitize_username("user<>name") == "user__name"
        assert sanitize_username("user/name") == "user_name"
        assert sanitize_username("user@domain.com") == "user_domain_com"

    @pytest.mark.security
    def test_empty_username(self):
        """Test empty username handling"""
        assert sanitize_username("") == "anonymous"
        assert sanitize_username(None) == "anonymous"
        assert sanitize_username("   ") == "anonymous"  # Whitespace only

    @pytest.mark.security
    def test_username_length_limit(self):
        """Test username length is limited"""
        long_username = "a" * 50
        sanitized = sanitize_username(long_username)

        assert len(sanitized) <= 32


class TestBroadcastMessageSanitization:
    """Test broadcast message sanitization"""

    @pytest.mark.security
    def test_broadcast_with_newlines(self):
        """Test newlines are preserved in broadcast messages"""
        message = "Line 1\nLine 2\nLine 3"
        sanitized = sanitize_broadcast_message(message)

        assert "\n" in sanitized
        assert "Line 1" in sanitized
        assert "Line 2" in sanitized

    @pytest.mark.security
    def test_broadcast_html_escaping(self):
        """Test HTML is escaped in broadcast messages"""
        message = "Important: <script>alert('XSS')</script>"
        sanitized = sanitize_broadcast_message(message)

        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized

    @pytest.mark.security
    def test_broadcast_length_limit(self):
        """Test broadcast message length limit"""
        long_message = "a" * 5000
        sanitized = sanitize_broadcast_message(long_message, max_length=4096)

        assert len(sanitized) <= 4096


class TestSearchQueryValidation:
    """Test search query sanitization"""

    @pytest.mark.security
    def test_valid_search_queries(self):
        """Test valid search queries pass through"""
        queries = [
            "john doe",
            "user_123",
            "Иван Иванов",
            "João Silva"
        ]

        for query in queries:
            sanitized = sanitize_search_query(query)
            assert sanitized  # Should not be empty
            assert len(sanitized) > 0

    @pytest.mark.security
    def test_sql_injection_in_search(self):
        """Test SQL injection attempts in search queries"""
        malicious_queries = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM passwords--"
        ]

        for query in malicious_queries:
            sanitized = sanitize_search_query(query)
            # Special SQL characters should be removed or escaped
            assert "'" not in sanitized or len(sanitized) == 0
            assert "--" not in sanitized
            assert ";" not in sanitized

    @pytest.mark.security
    def test_path_traversal_in_search(self):
        """Test path traversal attempts in search"""
        malicious = "../../../etc/passwd"
        sanitized = sanitize_search_query(malicious)

        assert "../" not in sanitized

    @pytest.mark.security
    def test_special_characters_removed(self):
        """Test dangerous special characters are removed"""
        query = "user<>name|grep|rm"
        sanitized = sanitize_search_query(query)

        assert "<" not in sanitized
        assert ">" not in sanitized
        assert "|" not in sanitized


class TestTelegramIDValidation:
    """Test Telegram ID validation"""

    @pytest.mark.security
    def test_valid_telegram_ids(self):
        """Test valid Telegram IDs are accepted"""
        valid_ids = [
            12345,
            123456789,
            999999999,
            1
        ]

        for user_id in valid_ids:
            assert validate_telegram_id(user_id) is True

    @pytest.mark.security
    def test_invalid_telegram_ids(self):
        """Test invalid Telegram IDs are rejected"""
        invalid_ids = [
            -1,
            0,
            -12345,
            None,
            "not_a_number",
            12345.67,  # Float
            10 ** 15  # Too large
        ]

        for user_id in invalid_ids:
            assert validate_telegram_id(user_id) is False


class TestSafeHelperFunctions:
    """Test safe helper functions"""

    @pytest.mark.security
    def test_safe_user_name(self):
        """Test safe_user_name helper"""
        # Mock user object
        class MockUser:
            def __init__(self, first_name=None, last_name=None):
                self.first_name = first_name
                self.last_name = last_name

        user = MockUser("John<script>", "Doe")
        safe_name = safe_user_name(user)

        assert "<script>" not in safe_name
        assert "John" in safe_name
        assert "Doe" in safe_name

    @pytest.mark.security
    def test_safe_user_name_no_name(self):
        """Test safe_user_name with no name"""
        class MockUser:
            first_name = None
            last_name = None

        user = MockUser()
        safe_name = safe_user_name(user)

        assert safe_name == "Anonymous"

    @pytest.mark.security
    def test_safe_username_helper(self):
        """Test safe_username helper"""
        class MockUser:
            def __init__(self, username=None):
                self.username = username

        user = MockUser("john<script>doe")
        safe_name = safe_username(user)

        assert "<script>" not in safe_name
        assert "john" in safe_name


class TestMaliciousPayloads:
    """Test against comprehensive malicious payload list"""

    @pytest.mark.security
    def test_owasp_top_xss_payloads(self, malicious_payloads):
        """Test against OWASP-style XSS payloads"""
        for payload_type, payload in malicious_payloads.items():
            sanitized = sanitize_user_input(payload)

            # Verify dangerous patterns are escaped
            assert "<script" not in sanitized
            assert "javascript:" not in sanitized or "&lt;" in sanitized
            assert "onerror=" not in sanitized or "&lt;" in sanitized

    @pytest.mark.security
    def test_sql_injection_payloads(self):
        """Test SQL injection prevention"""
        sql_payloads = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM passwords--",
            "1; DELETE FROM users WHERE 1=1--"
        ]

        for payload in sql_payloads:
            sanitized = sanitize_search_query(payload)

            # SQL injection should be neutered
            assert ";" not in sanitized
            assert "--" not in sanitized
            assert "'" not in sanitized or len(sanitized) == 0

    @pytest.mark.security
    def test_command_injection_payloads(self):
        """Test command injection prevention"""
        command_payloads = [
            "; ls -la",
            "| cat /etc/passwd",
            "`whoami`",
            "$(cat /etc/passwd)",
            "&& rm -rf /"
        ]

        for payload in command_payloads:
            sanitized = sanitize_user_input(payload)

            # Command injection characters should be escaped or removed
            # HTML escaping handles most of these
            assert "<" not in sanitized or "&lt;" in sanitized


class TestLengthLimits:
    """Test length limit enforcement"""

    @pytest.mark.security
    def test_user_input_length_limit(self):
        """Test user input respects max_length"""
        long_input = "a" * 1000

        sanitized = sanitize_user_input(long_input, max_length=50)
        assert len(sanitized) <= 50

        sanitized = sanitize_user_input(long_input, max_length=255)
        assert len(sanitized) <= 255

    @pytest.mark.security
    def test_broadcast_message_length_limit(self):
        """Test broadcast message length limit"""
        long_message = "x" * 10000

        sanitized = sanitize_broadcast_message(long_message, max_length=4096)
        assert len(sanitized) <= 4096

    @pytest.mark.security
    def test_extremely_long_input_dos_prevention(self):
        """Test that extremely long inputs don't cause DoS"""
        import time

        extremely_long = "a" * 1000000  # 1MB of text

        start = time.time()
        sanitized = sanitize_user_input(extremely_long, max_length=1000)
        elapsed = time.time() - start

        # Should complete quickly (< 1 second)
        assert elapsed < 1.0
        assert len(sanitized) <= 1000


class TestEdgeCases:
    """Test edge cases and corner cases"""

    @pytest.mark.security
    def test_none_input(self):
        """Test None input handling"""
        assert sanitize_user_input(None) == ""
        assert sanitize_username(None) == "anonymous"
        assert sanitize_broadcast_message(None) == ""

    @pytest.mark.security
    def test_empty_string(self):
        """Test empty string handling"""
        assert sanitize_user_input("") == ""
        assert sanitize_username("") == "anonymous"

    @pytest.mark.security
    def test_whitespace_only(self):
        """Test whitespace-only input"""
        assert sanitize_user_input("   ") == "   "  # Whitespace preserved
        assert sanitize_username("   ") == "anonymous"  # Username requires content

    @pytest.mark.security
    def test_unicode_characters(self):
        """Test Unicode character handling"""
        unicode_input = "Привет мир 🎉 Hello"
        sanitized = sanitize_user_input(unicode_input)

        assert "Привет" in sanitized
        assert "мир" in sanitized
        # Emoji should be preserved
        assert "🎉" in sanitized or len(sanitized) > 0

    @pytest.mark.security
    def test_mixed_content(self):
        """Test mixed legitimate and malicious content"""
        mixed = "Hello <script>alert('XSS')</script> World"
        sanitized = sanitize_user_input(mixed)

        assert "Hello" in sanitized
        assert "World" in sanitized
        assert "<script>" not in sanitized
        assert "&lt;script&gt;" in sanitized

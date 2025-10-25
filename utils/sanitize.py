"""
Input Sanitization Utilities

HIGH-003 FIX: Prevent HTML injection and XSS attacks
Sanitizes all user-provided input before display

Author: Production Readiness Team
Date: 2025-10-25
Version: 3.1
"""

from html import escape
import re
from typing import Optional

from utils.logger import logger


def sanitize_user_input(
    text: Optional[str],
    max_length: int = 255,
    allow_newlines: bool = False
) -> str:
    """
    Sanitize user input by escaping HTML and limiting length

    Prevents HTML injection attacks in Telegram HTML-formatted messages.

    Args:
        text: User input text
        max_length: Maximum allowed length
        allow_newlines: Whether to preserve newline characters

    Returns:
        Sanitized text safe for HTML display

    Example:
        >>> sanitize_user_input("<script>alert(1)</script>")
        "&lt;script&gt;alert(1)&lt;/script&gt;"

        >>> sanitize_user_input("<b>Bold Text</b>")
        "&lt;b&gt;Bold Text&lt;/b&gt;"
    """
    if not text:
        return ""

    # Truncate to max length
    text = text[:max_length]

    # Remove newlines if not allowed
    if not allow_newlines:
        text = text.replace("\n", " ").replace("\r", " ")

    # Escape HTML special characters
    # This converts: < > & " ' to HTML entities
    sanitized = escape(text)

    return sanitized


def sanitize_callback_data(data: Optional[str]) -> str:
    """
    Validate and sanitize callback data

    Callback data should only contain safe characters.
    Blocks potentially malicious callback data patterns.

    Args:
        data: Callback data string

    Returns:
        Sanitized callback data, or "invalid" if malicious

    Example:
        >>> sanitize_callback_data("general_info_menu")
        "general_info_menu"

        >>> sanitize_callback_data("<script>evil</script>")
        "invalid"
    """
    if not data:
        return ""

    # Only allow alphanumeric, underscore, hyphen, and colon
    # This covers all legitimate callback patterns
    if not re.match(r'^[a-zA-Z0-9_\-:]+$', data):
        logger.warning(
            f"⚠️ SECURITY: Invalid callback data blocked: {data[:50]}"
        )
        return "invalid"

    # Limit length to prevent abuse
    return data[:64]


def sanitize_username(username: Optional[str]) -> str:
    """
    Sanitize Telegram username

    Usernames can only contain letters, numbers, and underscores.

    Args:
        username: Telegram username

    Returns:
        Sanitized username

    Example:
        >>> sanitize_username("@valid_user123")
        "valid_user123"

        >>> sanitize_username("<script>evil</script>")
        "script_evil_script"
    """
    if not username:
        return "anonymous"

    # Check for whitespace-only strings
    if username.strip() == "":
        return "anonymous"

    # Remove @ prefix if present
    if username.startswith("@"):
        username = username[1:]

    # Keep only alphanumeric and underscores
    username = re.sub(r'[^a-zA-Z0-9_]', '_', username)

    # Limit length
    username = username[:32]

    # Remove leading/trailing underscores and check if anything remains
    cleaned = username.strip('_')

    return cleaned or "anonymous"


def sanitize_broadcast_message(text: str, max_length: int = 4096) -> str:
    """
    Sanitize broadcast message text

    Allows newlines but escapes HTML to prevent injection.

    Args:
        text: Broadcast message text
        max_length: Maximum message length (Telegram limit: 4096)

    Returns:
        Sanitized broadcast message

    Example:
        >>> sanitize_broadcast_message("Hello\\nWorld!")
        "Hello\\nWorld!"

        >>> sanitize_broadcast_message("<b>Admin</b> announcement")
        "&lt;b&gt;Admin&lt;/b&gt; announcement"
    """
    return sanitize_user_input(text, max_length=max_length, allow_newlines=True)


def validate_telegram_id(telegram_id: any) -> bool:
    """
    Validate Telegram user ID

    Telegram IDs are positive integers up to 10 digits.

    Args:
        telegram_id: User ID to validate

    Returns:
        True if valid, False otherwise

    Example:
        >>> validate_telegram_id(123456789)
        True

        >>> validate_telegram_id(-1)
        False

        >>> validate_telegram_id("not_a_number")
        False
    """
    try:
        # Reject floats - must be actual integers
        if isinstance(telegram_id, float):
            return False

        user_id = int(telegram_id)

        # Telegram IDs are positive and up to 10 digits
        return 0 < user_id < 10_000_000_000
    except (ValueError, TypeError):
        return False


def sanitize_search_query(query: str) -> str:
    """
    Sanitize search query input

    Removes special characters that could be used for injection.

    Args:
        query: Search query string

    Returns:
        Sanitized search query

    Example:
        >>> sanitize_search_query("normal search")
        "normal search"

        >>> sanitize_search_query("'; DROP TABLE users; --")
        " DROP TABLE users "
    """
    if not query:
        return ""

    # Remove path traversal sequences
    query = query.replace("../", "").replace("..\\", "")

    # Remove potentially dangerous SQL characters
    # (Even though we use ORM, defense in depth)
    dangerous_chars = ["'", '"', ";", "--", "/*", "*/", "\\"]
    for char in dangerous_chars:
        query = query.replace(char, " ")

    # Remove shell command special characters
    shell_chars = ["<", ">", "|", "&", "$", "`"]
    for char in shell_chars:
        query = query.replace(char, "")

    # Limit length
    query = query[:255]

    # Normalize whitespace
    query = " ".join(query.split())

    return query


# Convenience functions for common use cases
def safe_user_name(user) -> str:
    """
    Get safe display name from Telegram user object

    Args:
        user: Telegram User object (from message.from_user)

    Returns:
        Safe display name

    Example:
        >>> safe_user_name(user)
        "John Doe"
    """
    if not user:
        return "Anonymous"

    first = sanitize_user_input(user.first_name, max_length=50) if user.first_name else ""
    last = sanitize_user_input(user.last_name, max_length=50) if user.last_name else ""

    name = f"{first} {last}".strip()
    return name or "Anonymous"


def safe_username(user) -> str:
    """
    Get safe username from Telegram user object

    Args:
        user: Telegram User object

    Returns:
        Safe username with @ prefix

    Example:
        >>> safe_username(user)
        "@john_doe"
    """
    if not user or not user.username:
        return "без username"

    username = sanitize_username(user.username)
    return f"@{username}"


__all__ = [
    "sanitize_user_input",
    "sanitize_callback_data",
    "sanitize_username",
    "sanitize_broadcast_message",
    "validate_telegram_id",
    "sanitize_search_query",
    "safe_user_name",
    "safe_username"
]

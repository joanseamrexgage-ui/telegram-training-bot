"""
Unit tests for configuration

Run with: pytest tests/test_config.py -v
"""

import pytest
import os
from pathlib import Path

from config import load_config, TgBot, Database, RateLimit, Paths, Config


def test_load_config_with_valid_token(monkeypatch):
    """Test loading config with valid BOT_TOKEN"""
    # Set environment variables
    monkeypatch.setenv("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setenv("ADMIN_PASSWORD", "test_password")
    monkeypatch.setenv("ADMIN_IDS", "123456789,987654321")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db")

    config = load_config()

    assert config is not None
    assert isinstance(config, Config)
    assert config.tg_bot.token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert config.tg_bot.admin_password == "test_password"
    assert 123456789 in config.tg_bot.admin_ids
    assert 987654321 in config.tg_bot.admin_ids


def test_load_config_without_token(monkeypatch):
    """Test loading config without BOT_TOKEN raises error"""
    # Clear BOT_TOKEN
    monkeypatch.delenv("BOT_TOKEN", raising=False)

    with pytest.raises(ValueError, match="BOT_TOKEN"):
        load_config()


def test_default_values(monkeypatch):
    """Test that default values are loaded correctly"""
    monkeypatch.setenv("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")

    config = load_config()

    # Check default values
    assert config.db.url == "sqlite+aiosqlite:///./bot.db"
    assert config.rate_limit.messages == 3
    assert config.rate_limit.callbacks == 5
    assert config.log_level == "INFO"
    assert config.debug is False


def test_paths_ensure_exists(tmp_path):
    """Test that Paths.ensure_exists() creates directories"""
    content_dir = tmp_path / "content"
    logs_dir = tmp_path / "logs"

    paths = Paths(
        content=content_dir,
        logs=logs_dir,
        media=content_dir / "media",
        documents=content_dir / "media" / "documents"
    )

    # Ensure directories don't exist yet
    assert not content_dir.exists()
    assert not logs_dir.exists()

    # Call ensure_exists
    paths.ensure_exists()

    # Check that directories were created
    assert content_dir.exists()
    assert logs_dir.exists()
    assert (content_dir / "media").exists()
    assert (content_dir / "media" / "documents").exists()


def test_database_is_sqlite():
    """Test Database.is_sqlite property"""
    # SQLite database
    db_sqlite = Database(url="sqlite+aiosqlite:///./bot.db")
    assert db_sqlite.is_sqlite is True

    # PostgreSQL database
    db_postgres = Database(url="postgresql+asyncpg://user:pass@localhost/db")
    assert db_postgres.is_sqlite is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""
Unit tests for CRUD operations

Run with: pytest tests/test_crud.py -v
"""

import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from database.models import Base, User, UserActivity
from database.crud import UserCRUD, ActivityCRUD


# Fixture for test database
@pytest.fixture
async def db_session():
    """Create a test database session"""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session maker
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Provide session
    async with async_session() as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_user(db_session):
    """Test creating a new user"""
    user = await UserCRUD.get_or_create_user(
        session=db_session,
        telegram_id=123456789,
        username="test_user",
        first_name="Test",
        last_name="User"
    )

    assert user is not None
    assert user.telegram_id == 123456789
    assert user.username == "test_user"
    assert user.first_name == "Test"
    assert user.last_name == "User"
    assert user.is_blocked is False


@pytest.mark.asyncio
async def test_get_existing_user(db_session):
    """Test getting an existing user"""
    # Create user first
    user1 = await UserCRUD.get_or_create_user(
        session=db_session,
        telegram_id=123456789,
        username="test_user"
    )

    # Get the same user again
    user2 = await UserCRUD.get_or_create_user(
        session=db_session,
        telegram_id=123456789,
        username="test_user_updated"
    )

    assert user1.id == user2.id
    assert user2.username == "test_user_updated"  # Should be updated


@pytest.mark.asyncio
async def test_block_unblock_user(db_session):
    """Test blocking and unblocking a user"""
    # Create user
    user = await UserCRUD.get_or_create_user(
        session=db_session,
        telegram_id=123456789,
        username="test_user"
    )

    # Block user
    success = await UserCRUD.block_user(
        session=db_session,
        telegram_id=123456789,
        reason="Test block"
    )

    assert success is True

    # Check if user is blocked
    is_blocked = await UserCRUD.is_user_blocked(
        session=db_session,
        telegram_id=123456789
    )

    assert is_blocked is True

    # Unblock user
    success = await UserCRUD.unblock_user(
        session=db_session,
        telegram_id=123456789
    )

    assert success is True

    # Check if user is unblocked
    is_blocked = await UserCRUD.is_user_blocked(
        session=db_session,
        telegram_id=123456789
    )

    assert is_blocked is False


@pytest.mark.asyncio
async def test_log_activity(db_session):
    """Test logging user activity"""
    # Create user
    user = await UserCRUD.get_or_create_user(
        session=db_session,
        telegram_id=123456789,
        username="test_user"
    )

    # Log activity
    await ActivityCRUD.log_activity(
        session=db_session,
        user_id=user.id,
        action="test_action",
        section="test_section",
        details={"key": "value"}
    )

    # Get activities
    activities = await ActivityCRUD.get_user_activity(
        session=db_session,
        user_id=user.id,
        limit=10
    )

    assert len(activities) == 1
    assert activities[0].action == "test_action"
    assert activities[0].section == "test_section"


@pytest.mark.asyncio
async def test_get_users_count(db_session):
    """Test getting user count"""
    # Create multiple users
    for i in range(5):
        await UserCRUD.get_or_create_user(
            session=db_session,
            telegram_id=i,
            username=f"user_{i}"
        )

    # Get count
    count = await UserCRUD.get_users_count(db_session)

    assert count == 5


@pytest.mark.asyncio
async def test_user_full_name_property():
    """Test User model full_name property"""
    user = User(
        telegram_id=123,
        first_name="John",
        last_name="Doe"
    )

    assert user.full_name == "John Doe"

    # Test with only first name
    user2 = User(
        telegram_id=456,
        first_name="Jane"
    )

    assert user2.full_name == "Jane"

    # Test with no names
    user3 = User(telegram_id=789)

    assert user3.full_name == "User 789"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])

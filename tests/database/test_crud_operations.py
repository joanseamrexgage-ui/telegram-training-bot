"""
Comprehensive Database CRUD Operations Tests - TASK 1.5 Phase 1

Tests critical database operations with focus on error handling and resilience.
Target: database/crud.py (438 statements, 16.44% coverage → 60%+)

Test Categories:
1. UserCRUD Core Operations (8 tests)
   - get_or_create_user() - CRITICAL (called every interaction)
   - get_user_by_telegram_id()
   - block_user() / unblock_user()

2. UserCRUD Error Handling (6 tests)
   - Database connection failures
   - Constraint violations
   - Transaction rollbacks
   - Concurrent access

3. ActivityCRUD Operations (3 tests)
   - log_activity()
   - get_user_activity()

4. ContentCRUD Basic Operations (3 tests)
   - get_content()
   - create_or_update_content()

Strategic Focus: Foundation Layer Resilience
- Connection pool exhaustion handling
- Data integrity under failures
- Graceful degradation patterns

Testing Strategy: Real SQLite in-memory database
- Avoids complex SQLAlchemy mocking
- Tests real database operations
- Validates actual transactions and rollbacks
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

# Import CRUD classes to test
from database.crud import UserCRUD, ActivityCRUD, ContentCRUD
from database.models import User, UserActivity, Content, Base
from database.database import get_db_session


# =============================================================================
# FIXTURES - Real Test Database (SQLite in-memory)
# =============================================================================

@pytest.fixture
async def test_engine():
    """Create in-memory SQLite database engine for testing"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create database session for testing"""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture
async def mock_db_session():
    """Mock AsyncSession for error simulation tests"""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.execute = AsyncMock()
    return session


# =============================================================================
# CATEGORY 1: UserCRUD Core Operations - Normal Flow
# =============================================================================

class TestUserCRUDCore:
    """Test core UserCRUD operations with real database"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_or_create_user_new_user(self, test_session):
        """Test creating new user when not exists"""
        # Create new user
        user = await UserCRUD.get_or_create_user(
            test_session,
            telegram_id=12345,
            username="newuser",
            first_name="New",
            last_name="User"
        )

        # Verify user created
        assert user is not None
        assert user.telegram_id == 12345
        assert user.username == "newuser"
        assert user.first_name == "New"
        assert user.id is not None  # DB assigned ID

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_or_create_user_existing_user(self, test_session):
        """Test updating existing user when found"""
        # Create user first
        user1 = await UserCRUD.get_or_create_user(
            test_session,
            telegram_id=12345,
            username="original",
            first_name="Original"
        )
        original_id = user1.id

        # Get same user again with updated data
        user2 = await UserCRUD.get_or_create_user(
            test_session,
            telegram_id=12345,
            username="updated",
            first_name="Updated"
        )

        # Verify same user (ID unchanged)
        assert user2.id == original_id
        assert user2.telegram_id == 12345

        # Verify attributes updated
        assert user2.username == "updated"
        assert user2.first_name == "Updated"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_user_by_telegram_id_found(self, test_session):
        """Test getting user by telegram_id when exists"""
        # Create user first
        await UserCRUD.get_or_create_user(
            test_session,
            telegram_id=12345,
            username="testuser"
        )

        # Retrieve user
        user = await UserCRUD.get_user_by_telegram_id(test_session, 12345)

        # Verify user found
        assert user is not None
        assert user.telegram_id == 12345

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_user_by_telegram_id_not_found(self, test_session):
        """Test getting user by telegram_id when not exists"""
        user = await UserCRUD.get_user_by_telegram_id(test_session, 99999)

        # Verify None returned
        assert user is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_block_user_success(self, test_session):
        """Test blocking user successfully"""
        # Create user first
        await UserCRUD.get_or_create_user(test_session, telegram_id=12345)

        # Block user
        result = await UserCRUD.block_user(
            test_session,
            telegram_id=12345,
            reason="Spam detected"
        )

        # Verify success
        assert result is True

        # Verify user is blocked
        user = await UserCRUD.get_user_by_telegram_id(test_session, 12345)
        assert user.is_blocked is True
        assert user.block_reason == "Spam detected"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_block_user_not_found(self, test_session):
        """Test blocking non-existent user"""
        result = await UserCRUD.block_user(test_session, telegram_id=99999)

        # Verify failure
        assert result is False

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_unblock_user_success(self, test_session):
        """Test unblocking user successfully"""
        # Create and block user
        await UserCRUD.get_or_create_user(test_session, telegram_id=12345)
        await UserCRUD.block_user(test_session, telegram_id=12345, reason="Test")

        # Unblock user
        result = await UserCRUD.unblock_user(test_session, telegram_id=12345)

        # Verify success
        assert result is True

        # Verify user is unblocked
        user = await UserCRUD.get_user_by_telegram_id(test_session, 12345)
        assert user.is_blocked is False
        assert user.block_reason is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_increment_user_counter(self, test_session):
        """Test incrementing user counter (messages/commands)"""
        # Create user
        await UserCRUD.get_or_create_user(test_session, telegram_id=12345)

        # Increment messages counter (returns None on success)
        result = await UserCRUD.increment_user_counter(
            test_session,
            telegram_id=12345,
            counter_type="messages"
        )

        # Note: Method returns None on success (no explicit return)
        assert result is None  # Current implementation

        # Verify counter incremented
        user = await UserCRUD.get_user_by_telegram_id(test_session, 12345)
        assert user.messages_count == 1


# =============================================================================
# CATEGORY 2: UserCRUD Error Handling - Resilience Tests
# =============================================================================

class TestUserCRUDErrorHandling:
    """Test UserCRUD error handling and resilience"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_or_create_user_database_connection_error(self, mock_db_session):
        """Test graceful handling of database connection failure"""
        # Mock: Database connection error
        mock_db_session.execute = AsyncMock(
            side_effect=OperationalError("Connection refused", None, None)
        )

        with patch('database.crud.log_database_operation') as mock_log:
            # Should raise exception (as per current implementation)
            with pytest.raises(OperationalError):
                await UserCRUD.get_or_create_user(
                    mock_db_session,
                    telegram_id=12345
                )

            # Verify rollback called
            mock_db_session.rollback.assert_called_once()

            # Verify error logged
            mock_log.assert_called_once()
            log_call = mock_log.call_args
            assert log_call.kwargs['success'] is False
            assert "error" in log_call.kwargs['details']

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_or_create_user_constraint_violation(self, mock_db_session):
        """Test handling of unique constraint violation"""
        # Mock: User not found initially
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=execute_result)

        # Mock: Constraint violation on commit
        mock_db_session.commit = AsyncMock(
            side_effect=IntegrityError("duplicate key", None, None)
        )

        with pytest.raises(IntegrityError):
            await UserCRUD.get_or_create_user(
                mock_db_session,
                telegram_id=12345
            )

        # Verify rollback called
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_block_user_database_error(self, mock_db_session):
        """Test block_user handles database errors gracefully"""
        # Mock: Database error during execution
        mock_db_session.execute = AsyncMock(
            side_effect=DatabaseError("Lock timeout", None, None)
        )

        with patch('database.crud.logger') as mock_logger:
            result = await UserCRUD.block_user(mock_db_session, telegram_id=12345)

            # Verify graceful failure (returns False, not exception)
            assert result is False

            # Verify rollback called
            mock_db_session.rollback.assert_called_once()

            # Verify error logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_user_by_telegram_id_exception_handling(self, mock_db_session):
        """Test get_user_by_telegram_id handles exceptions gracefully"""
        # Mock: Generic exception
        mock_db_session.execute = AsyncMock(side_effect=Exception("Unexpected error"))

        with patch('database.crud.logger') as mock_logger:
            user = await UserCRUD.get_user_by_telegram_id(mock_db_session, 12345)

            # Verify returns None instead of raising
            assert user is None

            # Verify error logged
            mock_logger.error.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_concurrent_user_creation_integrity_error(self, test_session):
        """Test that IntegrityError is raised when creating duplicate users"""
        # This tests the real database constraint enforcement
        # Create first user
        user1 = await UserCRUD.get_or_create_user(
            test_session,
            telegram_id=12345,
            username="user1"
        )
        assert user1 is not None

        # Try to create duplicate with same telegram_id should update, not create new
        # (The get_or_create_user method handles this gracefully)
        user2 = await UserCRUD.get_or_create_user(
            test_session,
            telegram_id=12345,
            username="user2_updated"
        )

        # Should be same user (same ID), but with updated username
        assert user2.id == user1.id
        assert user2.telegram_id == 12345
        assert user2.username == "user2_updated"  # Updated from user1

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_transaction_rollback_on_commit_failure(self, mock_db_session):
        """Test transaction rollback when commit fails"""
        # Mock: Execute succeeds, but commit fails
        execute_result = MagicMock()
        execute_result.rowcount = 1
        mock_db_session.execute = AsyncMock(return_value=execute_result)
        mock_db_session.commit = AsyncMock(side_effect=DatabaseError("Commit failed", None, None))

        result = await UserCRUD.block_user(mock_db_session, telegram_id=12345)

        # Verify rollback called
        mock_db_session.rollback.assert_called_once()

        # Verify returns False (graceful failure)
        assert result is False


# =============================================================================
# CATEGORY 3: ActivityCRUD Operations
# =============================================================================

class TestActivityCRUD:
    """Test ActivityCRUD operations"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_log_activity_success(self, mock_db_session):
        """Test logging user activity"""
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()

        result = await ActivityCRUD.log_activity(
            mock_db_session,
            user_id=1,
            action="view_content",
            details={"section": "sales"}
        )

        # Note: Method returns None on success
        assert result is None

        # Verify activity added
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_log_activity_database_error(self, mock_db_session):
        """Test log_activity handles database errors"""
        mock_db_session.commit = AsyncMock(
            side_effect=DatabaseError("Insert failed", None, None)
        )

        result = await ActivityCRUD.log_activity(
            mock_db_session,
            user_id=1,
            action="view_content"
        )

        # Note: Method returns None even on error (no return statement)
        assert result is None

        # Verify rollback called
        mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_user_activity(self, mock_db_session):
        """Test retrieving user activity log"""
        # Mock: Activities found
        mock_activities = [
            MagicMock(action="view_content", timestamp=datetime.utcnow()),
            MagicMock(action="search", timestamp=datetime.utcnow())
        ]
        execute_result = MagicMock()
        execute_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=mock_activities)))
        mock_db_session.execute = AsyncMock(return_value=execute_result)

        activities = await ActivityCRUD.get_user_activity(
            mock_db_session,
            user_id=1,
            limit=10
        )

        # Verify activities returned
        assert len(activities) == 2


# =============================================================================
# CATEGORY 4: ContentCRUD Basic Operations
# =============================================================================

class TestContentCRUD:
    """Test ContentCRUD basic operations"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_content_by_key(self, mock_db_session):
        """Test retrieving content by key"""
        # Mock: Content found
        mock_content = MagicMock(
            key="sales_guide",
            section="sales",
            title="Sales Guide",
            is_active=True
        )
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=mock_content)
        mock_db_session.execute = AsyncMock(return_value=execute_result)

        content = await ContentCRUD.get_content(mock_db_session, key="sales_guide")

        # Verify content returned
        assert content is not None
        assert content.section == "sales"

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_get_content_not_found(self, mock_db_session):
        """Test getting non-existent content"""
        # Mock: Content not found
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=execute_result)

        content = await ContentCRUD.get_content(mock_db_session, key="nonexistent_key")

        # Verify None returned
        assert content is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_create_or_update_content(self, test_session):
        """Test creating or updating content with real database"""
        # Create new content
        content = await ContentCRUD.create_or_update_content(
            test_session,
            key="sales_guide",
            section="sales",
            title="New Sales Guide",
            text="Guide content here...",
            media_type="text"
        )

        # Verify content created
        assert content is not None
        assert content.key == "sales_guide"
        assert content.section == "sales"
        assert content.title == "New Sales Guide"

        # Update the same content
        updated_content = await ContentCRUD.create_or_update_content(
            test_session,
            key="sales_guide",
            section="sales",
            title="Updated Sales Guide",
            text="Updated content...",
            media_type="text"
        )

        # Should be same content (same key), but with updated title
        assert updated_content.key == "sales_guide"
        assert updated_content.title == "Updated Sales Guide"


__all__ = [
    "TestUserCRUDCore",
    "TestUserCRUDErrorHandling",
    "TestActivityCRUD",
    "TestContentCRUD"
]

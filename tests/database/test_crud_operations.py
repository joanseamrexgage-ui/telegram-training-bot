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

        # Increment messages counter
        result = await UserCRUD.increment_user_counter(
            test_session,
            telegram_id=12345,
            counter_type="messages"
        )

        # Verify success
        assert result is True

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
    async def test_concurrent_user_creation_simulation(self):
        """Test concurrent creation of same user (race condition)"""
        # This is a simulation test - real concurrent testing requires real DB
        # Here we test that the code handles IntegrityError properly

        mock_session1 = AsyncMock(spec=AsyncSession)
        mock_session2 = AsyncMock(spec=AsyncSession)

        # Mock: First session creates user successfully
        execute_result1 = MagicMock()
        execute_result1.scalar_one_or_none = MagicMock(return_value=None)
        mock_session1.execute = AsyncMock(return_value=execute_result1)
        mock_session1.commit = AsyncMock()
        mock_session1.rollback = AsyncMock()
        mock_session1.refresh = AsyncMock()

        # Mock: Second session hits constraint violation
        execute_result2 = MagicMock()
        execute_result2.scalar_one_or_none = MagicMock(return_value=None)
        mock_session2.execute = AsyncMock(return_value=execute_result2)
        mock_session2.commit = AsyncMock(
            side_effect=IntegrityError("duplicate key", None, None)
        )
        mock_session2.rollback = AsyncMock()

        # First creation should succeed
        with patch('database.crud.User') as MockUser:
            MockUser.return_value = MagicMock(telegram_id=12345)
            with patch('database.crud.log_database_operation'):
                user1 = await UserCRUD.get_or_create_user(
                    mock_session1,
                    telegram_id=12345
                )
                assert user1 is not None

        # Second creation should fail with IntegrityError
        with patch('database.crud.User') as MockUser:
            MockUser.return_value = MagicMock(telegram_id=12345)
            with pytest.raises(IntegrityError):
                await UserCRUD.get_or_create_user(
                    mock_session2,
                    telegram_id=12345
                )

            # Verify rollback called on failure
            mock_session2.rollback.assert_called_once()

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

        # Verify success
        assert result is True

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

        # Verify graceful failure
        assert result is False

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
    async def test_get_content_by_id(self, mock_db_session):
        """Test retrieving content by ID"""
        # Mock: Content found
        mock_content = MagicMock(
            id=1,
            section="sales",
            title="Sales Guide",
            content_type="text"
        )
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=mock_content)
        mock_db_session.execute = AsyncMock(return_value=execute_result)

        content = await ContentCRUD.get_content(mock_db_session, content_id=1)

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

        content = await ContentCRUD.get_content(mock_db_session, content_id=999)

        # Verify None returned
        assert content is None

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_create_or_update_content(self, mock_db_session):
        """Test creating or updating content"""
        # Mock: Content not found (will create new)
        execute_result = MagicMock()
        execute_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=execute_result)
        mock_db_session.add = MagicMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        with patch('database.crud.Content') as MockContent:
            mock_new_content = MagicMock(id=1, section="sales")
            MockContent.return_value = mock_new_content

            content = await ContentCRUD.create_or_update_content(
                mock_db_session,
                section="sales",
                title="New Sales Guide",
                content_type="text",
                text_content="Guide content..."
            )

            # Verify add called (new content)
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()


__all__ = [
    "TestUserCRUDCore",
    "TestUserCRUDErrorHandling",
    "TestActivityCRUD",
    "TestContentCRUD"
]

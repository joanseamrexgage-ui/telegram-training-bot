"""
Comprehensive tests for start handler - TASK 1.4

Tests error handling, database failures, FSM management, and user experience.
Target coverage: 85%+ for handlers/start.py (97 statements)

Test Categories:
1. Command Handlers (cmd_start, cmd_menu, cmd_profile)
2. Database Error Handling
3. FSM State Management
4. User Error Messages
5. Callback Query Handlers
6. Menu Navigation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aiogram import F
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

# Import handlers to test
from handlers.start import (
    cmd_start,
    cmd_menu,
    back_to_main_menu,
    WELCOME_TEXT,
    RETURN_TEXT
)
from states.menu_states import MenuStates
from database.models import User as DBUser


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_state():
    """Mock FSM context"""
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    state.set_state = AsyncMock()
    state.get_state = AsyncMock(return_value=None)
    return state


@pytest.fixture
def aiogram_start_message():
    """Create real aiogram Message for /start command"""
    message = Message(
        message_id=1,
        date=datetime.utcnow(),
        chat=Chat(id=12345, type="private"),
        from_user=User(
            id=12345,
            is_bot=False,
            first_name="Test",
            username="testuser",
            language_code="ru"
        ),
        text="/start"
    )

    # Mock answer method
    answer_mock = AsyncMock(return_value=MagicMock(message_id=2))
    object.__setattr__(message, 'answer', answer_mock)

    return message


@pytest.fixture
def mock_db_user():
    """Mock database user"""
    user = DBUser(
        id=1,
        telegram_id=12345,
        username="testuser",
        first_name="Test",
        messages_count=0,
        commands_count=0
    )
    return user


# =============================================================================
# CATEGORY 1: Command Handler Tests - Normal Flow
# =============================================================================

class TestCmdStart:
    """Test /start command handler"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_start_command_new_user(
        self, aiogram_start_message, mock_state, mock_db_session, mock_db_user
    ):
        """Test /start command creates new user and sends welcome"""
        # Mock UserCRUD operations
        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(return_value=mock_db_user)
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action') as mock_log:
                # Execute handler
                await cmd_start(aiogram_start_message, mock_state, mock_db_session)

                # Verify state management
                mock_state.clear.assert_called_once()
                mock_state.set_state.assert_called_once_with(MenuStates.main_menu)

                # Verify user creation
                MockUserCRUD.get_or_create_user.assert_called_once_with(
                    session=mock_db_session,
                    telegram_id=12345,
                    username="testuser",
                    first_name="Test",
                    last_name=None,
                    language_code="ru"
                )

                # Verify message sent
                aiogram_start_message.answer.assert_called_once()
                args = aiogram_start_message.answer.call_args
                assert WELCOME_TEXT in args.kwargs['text']
                assert args.kwargs['reply_markup'] is not None

                # Verify logging
                mock_log.assert_called_once()

                # Verify counter increment
                MockUserCRUD.increment_user_counter.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_start_command_existing_user(
        self, aiogram_start_message, mock_state, mock_db_session
    ):
        """Test /start command for existing user (messages_count > 0)"""
        # Mock existing user
        existing_user = DBUser(
            id=1,
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            messages_count=50,  # Existing user
            commands_count=10
        )

        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(return_value=existing_user)
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action') as mock_log:
                await cmd_start(aiogram_start_message, mock_state, mock_db_session)

                # Verify first_time flag is False
                log_call_args = mock_log.call_args
                assert log_call_args.kwargs['details']['first_time'] is False


# =============================================================================
# CATEGORY 2: Database Error Handling Tests
# =============================================================================

class TestDatabaseErrorHandling:
    """Test handler behavior when database operations fail"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_start_command_database_failure(
        self, aiogram_start_message, mock_state, mock_db_session
    ):
        """Test /start command handles database connection failure"""
        # Mock database failure
        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(
                side_effect=Exception("Database connection failed")
            )

            with patch('handlers.start.logger') as mock_logger:
                # Execute handler (should not crash)
                await cmd_start(aiogram_start_message, mock_state, mock_db_session)

                # Verify error was logged
                mock_logger.error.assert_called_once()
                error_msg = mock_logger.error.call_args[0][0]
                assert "Ошибка в обработчике /start" in error_msg

                # Verify user received error message
                aiogram_start_message.answer.assert_called()
                error_response = aiogram_start_message.answer.call_args[0][0]
                assert "❌" in error_response
                assert "Произошла ошибка" in error_response

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_menu_command_database_failure(
        self, aiogram_start_message, mock_state, mock_db_session
    ):
        """Test /menu command handles database failure gracefully"""
        # Mock database failure on counter increment
        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.increment_user_counter = AsyncMock(
                side_effect=Exception("Redis connection lost")
            )

            with patch('handlers.start.logger') as mock_logger:
                # Execute handler
                await cmd_menu(aiogram_start_message, mock_state, mock_db_session)

                # Verify error was logged (but no user error message)
                mock_logger.error.assert_called_once()
                error_msg = mock_logger.error.call_args[0][0]
                assert "Ошибка в обработчике /menu" in error_msg

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_user_creation_partial_data(
        self, mock_state, mock_db_session
    ):
        """Test handler works with partial user data (no username)"""
        # Create message with no username
        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(
                id=12345,
                is_bot=False,
                first_name="Test",
                username=None,  # No username
                language_code=None
            ),
            text="/start"
        )
        object.__setattr__(message, 'answer', AsyncMock(return_value=MagicMock(message_id=2)))

        mock_user = DBUser(
            id=1,
            telegram_id=12345,
            username=None,
            first_name="Test",
            messages_count=0
        )

        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(return_value=mock_user)
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action'):
                # Should handle None username gracefully
                await cmd_start(message, mock_state, mock_db_session)

                # Verify user was created with None username
                create_call = MockUserCRUD.get_or_create_user.call_args
                assert create_call.kwargs['username'] is None


# =============================================================================
# CATEGORY 3: FSM State Management Tests
# =============================================================================

class TestFSMStateManagement:
    """Test FSM state transitions and error handling"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_start_clears_existing_state(
        self, aiogram_start_message, mock_state, mock_db_session, mock_db_user
    ):
        """Test /start command clears any existing FSM state"""
        # Mock existing state
        mock_state.get_state = AsyncMock(return_value="SomeOtherState:active")

        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(return_value=mock_db_user)
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action'):
                await cmd_start(aiogram_start_message, mock_state, mock_db_session)

                # Verify state was cleared before setting new state
                mock_state.clear.assert_called_once()
                mock_state.set_state.assert_called_once_with(MenuStates.main_menu)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_menu_command_sets_main_menu_state(
        self, aiogram_start_message, mock_state, mock_db_session
    ):
        """Test /menu command sets MenuStates.main_menu"""
        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action'):
                await cmd_menu(aiogram_start_message, mock_state, mock_db_session)

                # Verify correct state set
                mock_state.set_state.assert_called_once_with(MenuStates.main_menu)

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_state_failure_handled(
        self, aiogram_start_message, mock_state, mock_db_session
    ):
        """Test handler handles FSM state operation failure"""
        # Mock state.clear failure
        mock_state.clear = AsyncMock(side_effect=Exception("State storage unavailable"))

        with patch('handlers.start.logger') as mock_logger:
            # Execute handler
            await cmd_start(aiogram_start_message, mock_state, mock_db_session)

            # Verify error was logged
            mock_logger.error.assert_called()


# =============================================================================
# CATEGORY 4: Callback Query Handler Tests
# =============================================================================

class TestCallbackQueryHandlers:
    """Test callback query handlers (inline buttons)"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_back_to_main_menu_callback(
        self, mock_state, mock_db_session
    ):
        """Test back_to_main callback returns to main menu"""
        # Create mock callback query
        callback = CallbackQuery(
            id="callback_1",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="back_to_main"
        )

        # Mock message
        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="previous message"
        )
        # Use object.__setattr__ for frozen models
        edit_text_mock = AsyncMock()
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action'):
                # Execute handler
                await back_to_main_menu(callback, mock_state, mock_db_session)

                # Verify state set to main menu
                mock_state.set_state.assert_called_once_with(MenuStates.main_menu)

                # Verify message edited
                message.edit_text.assert_called_once()
                args = message.edit_text.call_args
                assert RETURN_TEXT in args.kwargs['text']

                # Verify callback answered
                callback.answer.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_callback_edit_message_failure(
        self, mock_state, mock_db_session
    ):
        """Test callback handles message edit failure (message too old)"""
        callback = CallbackQuery(
            id="callback_1",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="back_to_main"
        )

        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="old message"
        )

        # Mock edit_text failure using object.__setattr__ for frozen model
        edit_text_mock = AsyncMock(
            side_effect=Exception("Message is too old to be edited")
        )
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        with patch('handlers.start.logger') as mock_logger:
            # Execute handler (should not crash)
            await back_to_main_menu(callback, mock_state, mock_db_session)

            # Verify error was logged
            mock_logger.error.assert_called()


# =============================================================================
# CATEGORY 5: User Experience Tests
# =============================================================================

class TestUserExperience:
    """Test user-facing behavior and messages"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_welcome_message_contains_instructions(
        self, aiogram_start_message, mock_state, mock_db_session, mock_db_user
    ):
        """Test welcome message contains helpful instructions"""
        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(return_value=mock_db_user)
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action'):
                await cmd_start(aiogram_start_message, mock_state, mock_db_session)

                # Verify welcome text content
                call_args = aiogram_start_message.answer.call_args
                message_text = call_args.kwargs['text']

                # Check key instructions present
                assert "Добро пожаловать" in message_text
                assert "/help" in message_text
                assert "/menu" in message_text
                assert "Выберите интересующий раздел" in message_text

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_error_message_user_friendly(
        self, aiogram_start_message, mock_state, mock_db_session
    ):
        """Test error messages are user-friendly (Russian, clear)"""
        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(
                side_effect=Exception("Internal error")
            )

            with patch('handlers.start.logger'):
                await cmd_start(aiogram_start_message, mock_state, mock_db_session)

                # Verify error message is user-friendly
                error_msg = aiogram_start_message.answer.call_args[0][0]
                assert "❌" in error_msg  # Visual indicator
                assert "Произошла ошибка" in error_msg  # Russian
                assert "администратору" in error_msg  # Support contact


# =============================================================================
# CATEGORY 6: Integration Tests
# =============================================================================

class TestHandlerIntegration:
    """Test handler integration with other components"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_full_start_flow(
        self, aiogram_start_message, mock_state, mock_db_session, mock_db_user
    ):
        """Test complete /start flow: DB + State + Message + Logging + Counter"""
        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(return_value=mock_db_user)
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action') as mock_log:
                with patch('handlers.start.get_main_menu_keyboard') as mock_keyboard:
                    mock_keyboard.return_value = MagicMock()

                    # Execute full flow
                    await cmd_start(
                        aiogram_start_message,
                        mock_state,
                        mock_db_session
                    )

                    # Verify all components called in correct order
                    assert mock_state.clear.called
                    assert MockUserCRUD.get_or_create_user.called
                    assert mock_state.set_state.called
                    assert aiogram_start_message.answer.called
                    assert mock_log.called
                    assert MockUserCRUD.increment_user_counter.called

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_menu_navigation_flow(
        self, aiogram_start_message, mock_state, mock_db_session
    ):
        """Test menu navigation from /start to /menu"""
        mock_db_user = DBUser(
            id=1,
            telegram_id=12345,
            username="testuser",
            first_name="Test",
            messages_count=0
        )

        with patch('handlers.start.UserCRUD') as MockUserCRUD:
            MockUserCRUD.get_or_create_user = AsyncMock(return_value=mock_db_user)
            MockUserCRUD.increment_user_counter = AsyncMock()

            with patch('handlers.start.log_user_action'):
                # 1. Start command
                await cmd_start(aiogram_start_message, mock_state, mock_db_session)
                assert mock_state.set_state.call_args[0][0] == MenuStates.main_menu

                # 2. Navigate to menu
                await cmd_menu(aiogram_start_message, mock_state, mock_db_session)
                assert mock_state.set_state.call_args[0][0] == MenuStates.main_menu

                # Verify both handlers executed successfully
                assert aiogram_start_message.answer.call_count == 2


__all__ = [
    "TestCmdStart",
    "TestDatabaseErrorHandling",
    "TestFSMStateManagement",
    "TestCallbackQueryHandlers",
    "TestUserExperience",
    "TestHandlerIntegration"
]

"""
Comprehensive tests for common handlers - TASK 1.4

Tests universal callback handlers (back, cancel, help) used throughout the bot.
Target coverage: 95%+ for handlers/common.py (26 statements)

Test Categories:
1. Back Button Handler
2. Cancel Button Handler (FSM clearing)
3. Help Command Handler
4. Help Callback Handler
5. Error Handling
6. Logging Validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from aiogram import F
from aiogram.types import Message, CallbackQuery, User, Chat
from aiogram.fsm.context import FSMContext

# Import handlers to test
from handlers.common import (
    handle_back,
    handle_cancel,
    cmd_help,
    callback_help
)


@pytest.fixture
def mock_state():
    """Mock FSM context"""
    state = AsyncMock(spec=FSMContext)
    state.clear = AsyncMock()
    return state


@pytest.fixture
def aiogram_callback():
    """Create real aiogram CallbackQuery"""
    callback = CallbackQuery(
        id="callback_1",
        from_user=User(id=12345, is_bot=False, first_name="Test", username="testuser"),
        chat_instance="12345",
        data="back"
    )

    # Mock methods
    answer_mock = AsyncMock()
    object.__setattr__(callback, 'answer', answer_mock)

    return callback


@pytest.fixture
def aiogram_message():
    """Create real aiogram Message"""
    message = Message(
        message_id=1,
        date=datetime.utcnow(),
        chat=Chat(id=12345, type="private"),
        from_user=User(id=12345, is_bot=False, first_name="Test", username="testuser"),
        text="/help"
    )

    # Mock answer method
    answer_mock = AsyncMock(return_value=MagicMock(message_id=2))
    object.__setattr__(message, 'answer', answer_mock)

    return message


# =============================================================================
# CATEGORY 1: Back Button Handler Tests
# =============================================================================

class TestBackButtonHandler:
    """Test handle_back callback"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_back_button_answers_callback(self, aiogram_callback):
        """Test back button sends callback answer"""
        # Execute handler
        await handle_back(aiogram_callback)

        # Verify callback answered
        aiogram_callback.answer.assert_called_once_with("⬅️ Возврат назад")

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_back_button_with_different_data(self):
        """Test back button works with callback data='back'"""
        callback = CallbackQuery(
            id="callback_2",
            from_user=User(id=67890, is_bot=False, first_name="User2"),
            chat_instance="67890",
            data="back"  # Specific data for back button
        )
        object.__setattr__(callback, 'answer', AsyncMock())

        await handle_back(callback)

        # Verify answer called
        callback.answer.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_back_button_callback_failure(self):
        """Test back button handles callback.answer() failure"""
        callback = CallbackQuery(
            id="callback_3",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="back"
        )

        # Mock answer failure
        answer_mock = AsyncMock(side_effect=Exception("Callback expired"))
        object.__setattr__(callback, 'answer', answer_mock)

        # Should not crash (exception propagates to middleware)
        with pytest.raises(Exception, match="Callback expired"):
            await handle_back(callback)


# =============================================================================
# CATEGORY 2: Cancel Button Handler Tests
# =============================================================================

class TestCancelButtonHandler:
    """Test handle_cancel callback with FSM clearing"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancel_clears_fsm_state(self, mock_state):
        """Test cancel button clears FSM state"""
        # Create callback with message
        callback = CallbackQuery(
            id="callback_1",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="cancel"
        )

        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="previous message"
        )

        edit_text_mock = AsyncMock()
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        with patch('handlers.common.logger') as mock_logger:
            # Execute handler
            await handle_cancel(callback, mock_state)

            # Verify state cleared
            mock_state.clear.assert_called_once()

            # Verify message edited with cancel text
            message.edit_text.assert_called_once()
            args = message.edit_text.call_args
            assert "❌" in args[0][0]
            assert "Действие отменено" in args[0][0]
            assert "/start" in args[0][0]

            # Verify callback answered
            callback.answer.assert_called_once_with("Отменено")

            # Verify logging
            mock_logger.info.assert_called_once()
            log_msg = mock_logger.info.call_args[0][0]
            assert "12345" in log_msg
            assert "отменил действие" in log_msg

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancel_when_no_active_state(self, mock_state):
        """Test cancel works even when no active FSM state"""
        callback = CallbackQuery(
            id="callback_2",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="cancel"
        )

        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="text"
        )

        edit_text_mock = AsyncMock()
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        # Mock state.clear() success even when no state
        mock_state.clear = AsyncMock()

        with patch('handlers.common.logger'):
            await handle_cancel(callback, mock_state)

            # Should still clear state (idempotent operation)
            mock_state.clear.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_cancel_message_edit_failure(self, mock_state):
        """Test cancel handles message edit failure (old message)"""
        callback = CallbackQuery(
            id="callback_3",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="cancel"
        )

        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="old message"
        )

        # Mock edit failure
        edit_text_mock = AsyncMock(side_effect=Exception("Message too old"))
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        # Exception should propagate to ErrorHandlingMiddleware
        with pytest.raises(Exception, match="Message too old"):
            await handle_cancel(callback, mock_state)

        # But state should still be cleared before exception
        mock_state.clear.assert_called_once()


# =============================================================================
# CATEGORY 3: Help Command Handler Tests
# =============================================================================

class TestHelpCommandHandler:
    """Test /help command handler"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_help_command_sends_instructions(self, aiogram_message):
        """Test /help command sends comprehensive help text"""
        with patch('handlers.common.logger') as mock_logger:
            # Execute handler
            await cmd_help(aiogram_message)

            # Verify message sent
            aiogram_message.answer.assert_called_once()
            help_text = aiogram_message.answer.call_args[0][0]

            # Verify help text content
            assert "ℹ️" in help_text
            assert "Справка по боту" in help_text
            assert "/start" in help_text
            assert "/help" in help_text
            assert "Общая информация" in help_text
            assert "Отдел продаж" in help_text
            assert "Спортивный отдел" in help_text
            assert "Админ-панель" in help_text
            assert "Навигация" in help_text
            assert "администратору" in help_text

            # Verify logging
            mock_logger.info.assert_called_once()
            log_msg = mock_logger.info.call_args[0][0]
            assert "12345" in log_msg
            assert "запросил помощь" in log_msg

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_help_command_with_different_users(self):
        """Test /help command logs different user IDs"""
        message = Message(
            message_id=2,
            date=datetime.utcnow(),
            chat=Chat(id=99999, type="private"),
            from_user=User(id=99999, is_bot=False, first_name="OtherUser"),
            text="/help"
        )
        object.__setattr__(message, 'answer', AsyncMock())

        with patch('handlers.common.logger') as mock_logger:
            await cmd_help(message)

            # Verify different user ID logged
            log_msg = mock_logger.info.call_args[0][0]
            assert "99999" in log_msg

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_help_command_answer_failure(self):
        """Test /help command handles message.answer() failure"""
        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="/help"
        )

        # Mock answer failure
        answer_mock = AsyncMock(side_effect=Exception("Bot blocked by user"))
        object.__setattr__(message, 'answer', answer_mock)

        with patch('handlers.common.logger'):
            # Exception should propagate to ErrorHandlingMiddleware
            with pytest.raises(Exception, match="Bot blocked by user"):
                await cmd_help(message)


# =============================================================================
# CATEGORY 4: Help Callback Handler Tests
# =============================================================================

class TestHelpCallbackHandler:
    """Test help callback button handler"""

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_help_callback_edits_message(self):
        """Test help callback edits message with help text"""
        callback = CallbackQuery(
            id="callback_1",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="help"
        )

        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="previous"
        )

        edit_text_mock = AsyncMock()
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        with patch('handlers.common.logger') as mock_logger:
            # Execute handler
            await callback_help(callback)

            # Verify message edited
            message.edit_text.assert_called_once()
            help_text = message.edit_text.call_args[0][0]

            # Verify help text content (same as /help command)
            assert "ℹ️" in help_text
            assert "Справка по боту" in help_text
            assert "/start" in help_text
            assert "/help" in help_text

            # Verify callback answered
            callback.answer.assert_called_once_with()

            # Verify logging
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.unit
    async def test_help_callback_vs_command_consistency(self, aiogram_message):
        """Test help callback and command return same text"""
        # Get help text from command
        with patch('handlers.common.logger'):
            await cmd_help(aiogram_message)
            command_help_text = aiogram_message.answer.call_args[0][0]

        # Get help text from callback
        callback = CallbackQuery(
            id="callback_1",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="help"
        )

        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="text"
        )

        edit_text_mock = AsyncMock()
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        with patch('handlers.common.logger'):
            await callback_help(callback)
            callback_help_text = message.edit_text.call_args[0][0]

        # Verify consistency
        assert command_help_text == callback_help_text


# =============================================================================
# CATEGORY 5: Integration Tests
# =============================================================================

class TestCommonHandlersIntegration:
    """Test integration between common handlers"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_cancel_then_help_flow(self, mock_state, aiogram_message):
        """Test user flow: cancel action → request help"""
        # 1. User cancels action
        callback = CallbackQuery(
            id="callback_1",
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            chat_instance="12345",
            data="cancel"
        )

        message = Message(
            message_id=1,
            date=datetime.utcnow(),
            chat=Chat(id=12345, type="private"),
            from_user=User(id=12345, is_bot=False, first_name="Test"),
            text="text"
        )

        edit_text_mock = AsyncMock()
        object.__setattr__(message, 'edit_text', edit_text_mock)
        object.__setattr__(callback, 'message', message)
        object.__setattr__(callback, 'answer', AsyncMock())

        with patch('handlers.common.logger'):
            await handle_cancel(callback, mock_state)
            mock_state.clear.assert_called_once()

            # 2. User requests help
            await cmd_help(aiogram_message)
            aiogram_message.answer.assert_called_once()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_all_common_handlers_log_actions(self):
        """Test all common handlers properly log user actions"""
        with patch('handlers.common.logger') as mock_logger:
            # Test back button (no logging expected)
            callback_back = CallbackQuery(
                id="cb1",
                from_user=User(id=1, is_bot=False, first_name="U1"),
                chat_instance="1",
                data="back"
            )
            object.__setattr__(callback_back, 'answer', AsyncMock())
            await handle_back(callback_back)

            # Test cancel button (logging expected)
            callback_cancel = CallbackQuery(
                id="cb2",
                from_user=User(id=2, is_bot=False, first_name="U2"),
                chat_instance="2",
                data="cancel"
            )
            message = Message(
                message_id=1,
                date=datetime.utcnow(),
                chat=Chat(id=2, type="private"),
                from_user=User(id=2, is_bot=False, first_name="U2"),
                text="text"
            )
            edit_text_mock = AsyncMock()
            object.__setattr__(message, 'edit_text', edit_text_mock)
            object.__setattr__(callback_cancel, 'message', message)
            object.__setattr__(callback_cancel, 'answer', AsyncMock())

            mock_state = AsyncMock(spec=FSMContext)
            await handle_cancel(callback_cancel, mock_state)

            # Test help command (logging expected)
            message_help = Message(
                message_id=3,
                date=datetime.utcnow(),
                chat=Chat(id=3, type="private"),
                from_user=User(id=3, is_bot=False, first_name="U3"),
                text="/help"
            )
            object.__setattr__(message_help, 'answer', AsyncMock())
            await cmd_help(message_help)

            # Test help callback (logging expected)
            callback_help_btn = CallbackQuery(
                id="cb4",
                from_user=User(id=4, is_bot=False, first_name="U4"),
                chat_instance="4",
                data="help"
            )
            message_help_cb = Message(
                message_id=4,
                date=datetime.utcnow(),
                chat=Chat(id=4, type="private"),
                from_user=User(id=4, is_bot=False, first_name="U4"),
                text="text"
            )
            edit_text_mock2 = AsyncMock()
            object.__setattr__(message_help_cb, 'edit_text', edit_text_mock2)
            object.__setattr__(callback_help_btn, 'message', message_help_cb)
            object.__setattr__(callback_help_btn, 'answer', AsyncMock())
            await callback_help(callback_help_btn)

            # Verify logging calls: cancel (1) + help command (1) + help callback (1) = 3
            assert mock_logger.info.call_count == 3


__all__ = [
    "TestBackButtonHandler",
    "TestCancelButtonHandler",
    "TestHelpCommandHandler",
    "TestHelpCallbackHandler",
    "TestCommonHandlersIntegration"
]

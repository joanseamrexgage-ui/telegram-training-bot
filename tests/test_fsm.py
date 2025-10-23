"""
VERSION 2.0: Unit tests for FSM (Finite State Machine) functionality

Тесты для проверки:
- Переходов между состояниями
- Корректности состояний
- Работы FSM storage
- Функций-помощников для состояний

Run with: pytest tests/test_fsm.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import User, Chat

from states.menu_states import (
    MenuStates,
    TestStates,
    RegistrationStates,
    FeedbackStates,
    SearchStates,
    get_state_name,
    is_admin_state,
    is_test_state,
    get_readable_state_name,
)
from states.admin_states import AdminStates, ContentEditStates


@pytest.fixture
def storage():
    """Create a memory storage for FSM"""
    return MemoryStorage()


@pytest.fixture
def mock_user():
    """Create a mock user"""
    return User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="test_user"
    )


@pytest.fixture
def mock_chat():
    """Create a mock chat"""
    return Chat(id=123456789, type="private")


@pytest.fixture
async def fsm_context(storage, mock_user, mock_chat):
    """Create FSMContext for testing"""
    # Create a context for the user
    context = FSMContext(
        storage=storage,
        key=storage.key(
            bot_id=123,  # Mock bot ID
            chat_id=mock_chat.id,
            user_id=mock_user.id
        )
    )
    return context


class TestMenuStates:
    """Тесты для состояний меню"""

    @pytest.mark.asyncio
    async def test_main_menu_state(self, fsm_context):
        """Test setting and getting main menu state"""
        await fsm_context.set_state(MenuStates.main_menu)
        current_state = await fsm_context.get_state()

        assert current_state == "MenuStates:main_menu"

    @pytest.mark.asyncio
    async def test_general_info_state(self, fsm_context):
        """Test general info state transition"""
        await fsm_context.set_state(MenuStates.general_info)
        current_state = await fsm_context.get_state()

        assert current_state == "MenuStates:general_info"

    @pytest.mark.asyncio
    async def test_sales_department_states(self, fsm_context):
        """Test sales department state transitions"""
        # Navigate to sales department
        await fsm_context.set_state(MenuStates.sales_department)
        assert await fsm_context.get_state() == "MenuStates:sales_department"

        # Navigate to sales general info
        await fsm_context.set_state(MenuStates.sales_general_info)
        assert await fsm_context.get_state() == "MenuStates:sales_general_info"

        # Navigate to cash register
        await fsm_context.set_state(MenuStates.cash_register)
        assert await fsm_context.get_state() == "MenuStates:cash_register"

    @pytest.mark.asyncio
    async def test_sport_department_states(self, fsm_context):
        """Test sport department state transitions"""
        await fsm_context.set_state(MenuStates.sport_department)
        assert await fsm_context.get_state() == "MenuStates:sport_department"

        await fsm_context.set_state(MenuStates.sport_safety_rules)
        assert await fsm_context.get_state() == "MenuStates:sport_safety_rules"

    @pytest.mark.asyncio
    async def test_clear_state(self, fsm_context):
        """Test clearing FSM state"""
        await fsm_context.set_state(MenuStates.main_menu)
        assert await fsm_context.get_state() is not None

        await fsm_context.clear()
        assert await fsm_context.get_state() is None


class TestAdminStates:
    """Тесты для состояний администратора"""

    @pytest.mark.asyncio
    async def test_admin_password_request(self, fsm_context):
        """Test admin password request state"""
        await fsm_context.set_state(AdminStates.waiting_for_password)
        current_state = await fsm_context.get_state()

        assert current_state == "AdminStates:waiting_for_password"

    @pytest.mark.asyncio
    async def test_admin_authorized_state(self, fsm_context):
        """Test admin authorized state"""
        await fsm_context.set_state(AdminStates.authorized)
        assert await fsm_context.get_state() == "AdminStates:authorized"

    @pytest.mark.asyncio
    async def test_admin_broadcast_flow(self, fsm_context):
        """Test admin broadcast state flow"""
        # Start broadcast
        await fsm_context.set_state(AdminStates.broadcast_menu)
        assert await fsm_context.get_state() == "AdminStates:broadcast_menu"

        # Wait for text
        await fsm_context.set_state(AdminStates.broadcast_waiting_text)
        assert await fsm_context.get_state() == "AdminStates:broadcast_waiting_text"

        # Select target
        await fsm_context.set_state(AdminStates.broadcast_select_target)
        assert await fsm_context.get_state() == "AdminStates:broadcast_select_target"

        # Confirm
        await fsm_context.set_state(AdminStates.broadcast_confirm)
        assert await fsm_context.get_state() == "AdminStates:broadcast_confirm"

    @pytest.mark.asyncio
    async def test_admin_users_management(self, fsm_context):
        """Test admin users management states"""
        await fsm_context.set_state(AdminStates.users_menu)
        assert await fsm_context.get_state() == "AdminStates:users_menu"

        await fsm_context.set_state(AdminStates.users_viewing)
        assert await fsm_context.get_state() == "AdminStates:users_viewing"

        await fsm_context.set_state(AdminStates.users_blocking)
        assert await fsm_context.get_state() == "AdminStates:users_blocking"


class TestFSMData:
    """Тесты для хранения данных в FSM"""

    @pytest.mark.asyncio
    async def test_set_and_get_data(self, fsm_context):
        """Test setting and getting FSM data"""
        test_data = {
            "user_name": "John Doe",
            "department": "Sales",
            "park": "Park 1"
        }

        await fsm_context.update_data(**test_data)
        data = await fsm_context.get_data()

        assert data["user_name"] == "John Doe"
        assert data["department"] == "Sales"
        assert data["park"] == "Park 1"

    @pytest.mark.asyncio
    async def test_update_data(self, fsm_context):
        """Test updating FSM data"""
        await fsm_context.update_data(counter=1)
        data = await fsm_context.get_data()
        assert data["counter"] == 1

        await fsm_context.update_data(counter=2)
        data = await fsm_context.get_data()
        assert data["counter"] == 2

    @pytest.mark.asyncio
    async def test_clear_data(self, fsm_context):
        """Test clearing FSM data"""
        await fsm_context.update_data(test_key="test_value")
        data = await fsm_context.get_data()
        assert "test_key" in data

        await fsm_context.clear()
        data = await fsm_context.get_data()
        assert data == {}


class TestRegistrationStates:
    """Тесты для состояний регистрации"""

    @pytest.mark.asyncio
    async def test_registration_flow(self, fsm_context):
        """Test complete registration flow"""
        # Start with name
        await fsm_context.set_state(RegistrationStates.waiting_for_name)
        await fsm_context.update_data(name="John Doe")

        # Department
        await fsm_context.set_state(RegistrationStates.waiting_for_department)
        await fsm_context.update_data(department="Sales")

        # Park
        await fsm_context.set_state(RegistrationStates.waiting_for_park)
        await fsm_context.update_data(park="Park 1")

        # Confirm
        await fsm_context.set_state(RegistrationStates.confirm_registration)

        # Verify all data is stored
        data = await fsm_context.get_data()
        assert data["name"] == "John Doe"
        assert data["department"] == "Sales"
        assert data["park"] == "Park 1"


class TestStateHelperFunctions:
    """Тесты для вспомогательных функций состояний"""

    def test_get_state_name(self):
        """Test getting state name"""
        name = get_state_name(MenuStates.main_menu)
        assert name == "main_menu"

    def test_is_admin_state_true(self):
        """Test is_admin_state returns True for admin states"""
        assert is_admin_state(MenuStates.admin_panel) is True
        assert is_admin_state(MenuStates.admin_password_request) is True

    def test_is_admin_state_false(self):
        """Test is_admin_state returns False for non-admin states"""
        assert is_admin_state(MenuStates.main_menu) is False
        assert is_admin_state(MenuStates.sales_department) is False

    def test_is_test_state_true(self):
        """Test is_test_state returns True for test states"""
        assert is_test_state(TestStates.select_test_category) is True
        assert is_test_state(TestStates.test_in_progress) is True

    def test_is_test_state_false(self):
        """Test is_test_state returns False for non-test states"""
        assert is_test_state(MenuStates.main_menu) is False
        assert is_test_state(AdminStates.authorized) is False

    def test_get_readable_state_name(self):
        """Test getting readable state names"""
        assert get_readable_state_name(MenuStates.main_menu) == "Главное меню"
        assert get_readable_state_name(MenuStates.sales_department) == "Отдел продаж"
        assert get_readable_state_name(MenuStates.admin_panel) == "Админ-панель"


class TestContentEditStates:
    """Тесты для состояний редактирования контента"""

    @pytest.mark.asyncio
    async def test_content_edit_flow(self, fsm_context):
        """Test content editing flow"""
        # Wait for new text
        await fsm_context.set_state(ContentEditStates.waiting_new_text)
        assert await fsm_context.get_state() == "ContentEditStates:waiting_new_text"

        # Confirm changes
        await fsm_context.set_state(ContentEditStates.confirm_changes)
        assert await fsm_context.get_state() == "ContentEditStates:confirm_changes"

    @pytest.mark.asyncio
    async def test_media_upload_states(self, fsm_context):
        """Test media upload states"""
        # Video upload
        await fsm_context.set_state(ContentEditStates.waiting_video)
        assert await fsm_context.get_state() == "ContentEditStates:waiting_video"

        # Document upload
        await fsm_context.set_state(ContentEditStates.waiting_document)
        assert await fsm_context.get_state() == "ContentEditStates:waiting_document"

        # Image upload
        await fsm_context.set_state(ContentEditStates.waiting_image)
        assert await fsm_context.get_state() == "ContentEditStates:waiting_image"


class TestSearchAndFeedback:
    """Тесты для состояний поиска и обратной связи"""

    @pytest.mark.asyncio
    async def test_search_states(self, fsm_context):
        """Test search states"""
        await fsm_context.set_state(SearchStates.waiting_for_search_query)
        assert await fsm_context.get_state() == "SearchStates:waiting_for_search_query"

        await fsm_context.set_state(SearchStates.showing_search_results)
        assert await fsm_context.get_state() == "SearchStates:showing_search_results"

    @pytest.mark.asyncio
    async def test_feedback_flow(self, fsm_context):
        """Test feedback submission flow"""
        # Select feedback type
        await fsm_context.set_state(FeedbackStates.waiting_for_feedback_type)
        await fsm_context.update_data(feedback_type="bug")

        # Enter feedback text
        await fsm_context.set_state(FeedbackStates.waiting_for_feedback_text)
        await fsm_context.update_data(feedback_text="Found a bug in menu")

        # Confirm
        await fsm_context.set_state(FeedbackStates.confirm_feedback)

        # Verify data
        data = await fsm_context.get_data()
        assert data["feedback_type"] == "bug"
        assert data["feedback_text"] == "Found a bug in menu"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

"""
FSM состояния для навигации по меню бота
"""

from aiogram.fsm.state import State, StatesGroup


class MenuStates(StatesGroup):
    """Основные состояния меню"""
    
    # Главное меню
    main_menu = State()
    
    # ========== ОБЩАЯ ИНФОРМАЦИЯ ==========
    general_info = State()
    park_addresses = State()
    park_address_detail = State()  # Детальная информация о конкретном парке
    phone_numbers = State()
    emergency_actions = State()
    salary_info = State()
    park_orders = State()
    partner_discounts = State()
    
    # ========== ОТДЕЛ ПРОДАЖ ==========
    sales_department = State()
    
    # Подраздел: Общая информация
    sales_general_info = State()
    sales_structure = State()
    sales_appearance = State()
    sales_work_rules = State()
    sales_atmosphere = State()
    sales_schedule = State()
    sales_chats = State()
    
    # Подраздел: Открытие/закрытие парка
    park_opening_closing = State()
    park_opening_video = State()
    park_opening_checklist = State()
    park_closing_video = State()
    park_closing_checklist = State()
    
    # Подраздел: Работа с кассой
    cash_register = State()
    cash_register_video = State()
    cash_register_login = State()
    cash_register_order = State()
    cash_register_payment = State()
    cash_register_refund = State()
    cash_register_closing = State()
    cash_register_errors = State()
    
    # Подраздел: Работа с amoCRM
    amo_crm = State()
    amo_crm_video = State()
    amo_crm_login = State()
    amo_crm_deal = State()
    amo_crm_pipeline = State()
    amo_crm_tasks = State()
    amo_crm_client_card = State()
    amo_crm_tags = State()
    
    # Подраздел: Работа с гостями
    guest_relations = State()
    sales_scripts = State()
    sales_greeting = State()
    sales_needs = State()
    sales_presentation = State()
    objection_handling = State()
    sales_closing = State()
    upsell_techniques = State()
    work_with_children = State()
    work_with_adults = State()
    contact_collection = State()
    
    # Подраздел: Предупрежден — вооружен!
    security_warnings = State()
    fake_money = State()
    return_fraud = State()
    aggressive_clients = State()
    theft_prevention = State()
    unauthorized_access = State()
    
    # ========== СПОРТИВНЫЙ ОТДЕЛ ==========
    sport_department = State()
    sport_general_info = State()
    sport_structure = State()
    sport_safety_rules = State()
    equipment_operation = State()
    equipment_video = State()
    equipment_instructions = State()
    injury_protocol = State()
    first_aid = State()
    sport_schedule = State()
    sport_chats = State()
    
    # ========== АДМИНИСТРАЦИЯ ==========
    admin_password_request = State()
    admin_panel = State()
    
    # Админ: Управление контентом
    admin_content_management = State()
    admin_add_content = State()
    admin_edit_content = State()
    admin_delete_content = State()
    admin_upload_media = State()
    
    # Админ: Статистика
    admin_statistics = State()
    admin_user_stats = State()
    admin_activity_stats = State()
    admin_section_stats = State()
    admin_test_stats = State()
    
    # Админ: Управление пользователями
    admin_user_management = State()
    admin_user_list = State()
    admin_user_detail = State()
    admin_user_block = State()
    admin_user_unblock = State()
    admin_user_edit = State()
    
    # Админ: Рассылка
    admin_broadcast = State()
    admin_broadcast_create = State()
    admin_broadcast_target = State()
    admin_broadcast_preview = State()
    admin_broadcast_confirm = State()
    
    # Админ: Системные настройки
    admin_system_settings = State()
    admin_backup = State()
    admin_logs_view = State()


class TestStates(StatesGroup):
    """Состояния для системы тестирования"""
    
    # Выбор теста
    select_test_category = State()
    test_rules = State()
    test_confirm_start = State()
    
    # Процесс тестирования
    test_in_progress = State()
    test_question = State()
    test_answer_confirm = State()
    
    # Результаты
    test_results = State()
    test_review = State()
    test_certificate = State()


class RegistrationStates(StatesGroup):
    """Состояния для регистрации пользователя"""
    
    waiting_for_name = State()
    waiting_for_department = State()
    waiting_for_park = State()
    waiting_for_position = State()
    waiting_for_phone = State()
    waiting_for_email = State()
    confirm_registration = State()


class FeedbackStates(StatesGroup):
    """Состояния для обратной связи"""
    
    waiting_for_feedback_type = State()
    waiting_for_feedback_text = State()
    waiting_for_feedback_contact = State()
    confirm_feedback = State()


class SearchStates(StatesGroup):
    """Состояния для поиска"""
    
    waiting_for_search_query = State()
    showing_search_results = State()


# Вспомогательные функции для работы с состояниями
def get_state_name(state: State) -> str:
    """
    Получение читаемого имени состояния
    
    Args:
        state: Объект состояния
        
    Returns:
        str: Читаемое имя состояния
    """
    if state:
        return state.state.split(":")[-1] if ":" in state.state else state.state
    return "unknown"


def is_admin_state(state: State) -> bool:
    """
    Проверка, является ли состояние административным
    
    Args:
        state: Объект состояния
        
    Returns:
        bool: True если состояние административное
    """
    if state and hasattr(state, 'state'):
        return state.state.startswith("MenuStates:admin")
    return False


def is_test_state(state: State) -> bool:
    """
    Проверка, является ли состояние тестовым
    
    Args:
        state: Объект состояния
        
    Returns:
        bool: True если состояние относится к тестированию
    """
    if state and hasattr(state, 'state'):
        return "TestStates:" in state.state
    return False


# Маппинг состояний на читаемые названия (для логов и статистики)
STATE_NAMES = {
    MenuStates.main_menu: "Главное меню",
    MenuStates.general_info: "Общая информация",
    MenuStates.park_addresses: "Адреса парков",
    MenuStates.phone_numbers: "Телефонные номера",
    MenuStates.emergency_actions: "Внештатные ситуации",
    MenuStates.salary_info: "Информация о зарплате",
    MenuStates.park_orders: "Приказы парка",
    MenuStates.partner_discounts: "Скидки партнеров",
    
    MenuStates.sales_department: "Отдел продаж",
    MenuStates.sales_general_info: "Продажи: Общая информация",
    MenuStates.cash_register: "Работа с кассой",
    MenuStates.amo_crm: "Работа с amoCRM",
    MenuStates.guest_relations: "Работа с гостями",
    MenuStates.security_warnings: "Предупрежден - вооружен",
    
    MenuStates.sport_department: "Спортивный отдел",
    MenuStates.admin_panel: "Админ-панель",
    
    TestStates.select_test_category: "Выбор категории теста",
    TestStates.test_in_progress: "Прохождение теста",
    TestStates.test_results: "Результаты теста",
}


def get_readable_state_name(state: State) -> str:
    """
    Получение читаемого названия состояния на русском
    
    Args:
        state: Объект состояния
        
    Returns:
        str: Читаемое название состояния
    """
    return STATE_NAMES.get(state, get_state_name(state))

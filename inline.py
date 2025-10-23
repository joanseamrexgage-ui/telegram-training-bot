"""
Inline клавиатуры для навигации по меню бота
"""

from typing import Optional, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Главное меню бота"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="🟢 Общая информация", callback_data="general_info")
    builder.button(text="🔴 Отдел продаж", callback_data="sales")
    builder.button(text="🔵 Спортивный отдел", callback_data="sport")
    builder.button(text="🔐 Администрация парка", callback_data="admin")
    
    builder.adjust(1)  # По одной кнопке в ряд
    return builder.as_markup()


def get_general_info_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела 'Общая информация'"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📍 Адреса парков", callback_data="addresses")
    builder.button(text="📞 Важные номера телефонов", callback_data="phones")
    builder.button(text="🚨 Внештатные ситуации", callback_data="emergency")
    builder.button(text="💰 Аванс/Зарплата", callback_data="salary")
    builder.button(text="📋 Приказы парка", callback_data="orders")
    builder.button(text="🎁 Скидки у партнеров", callback_data="discounts")
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    
    builder.adjust(1)
    return builder.as_markup()


def get_park_selection_keyboard(action: str = "info") -> InlineKeyboardMarkup:
    """
    Выбор парка
    
    Args:
        action: Действие после выбора парка (info, phone, schedule)
    """
    builder = InlineKeyboardBuilder()
    
    builder.button(
        text="🏢 ТРЦ Зеленопарк", 
        callback_data=f"park_zeleniy_{action}"
    )
    builder.button(
        text="🏢 ТРЦ Каширская плаза", 
        callback_data=f"park_kashirskaya_{action}"
    )
    builder.button(
        text="🏢 ТРЦ Коламбус", 
        callback_data=f"park_columbus_{action}"
    )
    builder.button(text="◀️ Назад", callback_data="general_info")
    
    builder.adjust(1)
    return builder.as_markup()


def get_sales_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела 'Отдел продаж'"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="ℹ️ Общая информация", callback_data="sales_general")
    builder.button(text="🔓 Открытие/закрытие парка", callback_data="opening_closing")
    builder.button(text="💳 Работа с кассой", callback_data="cash_register")
    builder.button(text="💼 Работа с амоСРМ", callback_data="amo_crm")
    builder.button(text="👥 Работа с гостями", callback_data="guest_relations")
    builder.button(text="⚠️ Предупрежден - вооружен!", callback_data="warnings")
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    
    builder.adjust(1)
    return builder.as_markup()


def get_sales_general_info_keyboard() -> InlineKeyboardMarkup:
    """Меню подраздела 'Общая информация' в отделе продаж"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="👥 Оргструктура отдела", callback_data="sales_structure")
    builder.button(text="👔 Внешний вид сотрудников", callback_data="sales_appearance")
    builder.button(text="⏰ Правила прихода/ухода", callback_data="sales_work_rules")
    builder.button(text="🌟 Атмосфера в коллективе", callback_data="sales_atmosphere")
    builder.button(text="📅 График работы", callback_data="sales_schedule")
    builder.button(text="💬 Чаты отдела", callback_data="sales_chats")
    builder.button(text="◀️ Назад", callback_data="sales")
    
    builder.adjust(1)
    return builder.as_markup()


def get_cash_register_keyboard() -> InlineKeyboardMarkup:
    """Меню работы с кассой"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📹 Видео-инструкция", callback_data="cash_video")
    builder.button(text="🔑 Вход в систему", callback_data="cash_login")
    builder.button(text="🛒 Создание заказа", callback_data="cash_order")
    builder.button(text="💳 Прием платежей", callback_data="cash_payment")
    builder.button(text="↩️ Возврат средств", callback_data="cash_refund")
    builder.button(text="🔒 Закрытие кассы", callback_data="cash_closing")
    builder.button(text="❌ Типичные ошибки", callback_data="cash_errors")
    builder.button(text="◀️ Назад", callback_data="sales")
    
    builder.adjust(1)
    return builder.as_markup()


def get_amo_crm_keyboard() -> InlineKeyboardMarkup:
    """Меню работы с amoCRM"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📹 Видео-инструкция", callback_data="crm_video")
    builder.button(text="🔑 Вход в систему", callback_data="crm_login")
    builder.button(text="💼 Создание сделки", callback_data="crm_deal")
    builder.button(text="📊 Ведение воронки", callback_data="crm_pipeline")
    builder.button(text="📝 Работа с задачами", callback_data="crm_tasks")
    builder.button(text="👤 Карточка клиента", callback_data="crm_client")
    builder.button(text="🏷️ Использование тегов", callback_data="crm_tags")
    builder.button(text="◀️ Назад", callback_data="sales")
    
    builder.adjust(1)
    return builder.as_markup()


def get_guest_relations_keyboard() -> InlineKeyboardMarkup:
    """Меню работы с гостями"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📝 Скрипты продаж", callback_data="sales_scripts")
    builder.button(text="👋 Приветствие", callback_data="sales_greeting")
    builder.button(text="🎯 Выявление потребностей", callback_data="sales_needs")
    builder.button(text="🎁 Презентация услуг", callback_data="sales_presentation")
    builder.button(text="💬 Работа с возражениями", callback_data="objections")
    builder.button(text="✅ Завершение сделки", callback_data="sales_closing")
    builder.button(text="📈 Upsell техники", callback_data="upsell")
    builder.button(text="👶 Работа с детьми", callback_data="work_children")
    builder.button(text="👨‍👩‍👧 Работа со взрослыми", callback_data="work_adults")
    builder.button(text="📲 Сбор контактов", callback_data="contacts")
    builder.button(text="◀️ Назад", callback_data="sales")
    
    builder.adjust(2, 2, 2, 2, 2, 1)  # По 2 кнопки в ряд, последняя одна
    return builder.as_markup()


def get_warnings_keyboard() -> InlineKeyboardMarkup:
    """Меню раздела 'Предупрежден - вооружен'"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="💵 Фальшивые купюры", callback_data="fake_money")
    builder.button(text="↩️ Возвратные мошенники", callback_data="return_fraud")
    builder.button(text="😡 Агрессивные клиенты", callback_data="aggressive")
    builder.button(text="🚫 Кража и подозрительное поведение", callback_data="theft")
    builder.button(text="🎫 Попытки прохода без оплаты", callback_data="unauthorized")
    builder.button(text="◀️ Назад", callback_data="sales")
    
    builder.adjust(1)
    return builder.as_markup()


def get_sport_keyboard() -> InlineKeyboardMarkup:
    """Меню спортивного отдела"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="ℹ️ Общая информация", callback_data="sport_general")
    builder.button(text="⚠️ Правила безопасности", callback_data="sport_safety")
    builder.button(text="🎮 Эксплуатация оборудования", callback_data="equipment")
    builder.button(text="🏥 Действия при травмах", callback_data="injury")
    builder.button(text="📅 График работы", callback_data="sport_schedule")
    builder.button(text="💬 Чаты отдела", callback_data="sport_chats")
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    
    builder.adjust(1)
    return builder.as_markup()


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Меню админ-панели"""
    builder = InlineKeyboardBuilder()
    
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Управление пользователями", callback_data="admin_users")
    builder.button(text="📝 Управление контентом", callback_data="admin_content")
    builder.button(text="📢 Рассылка сообщений", callback_data="admin_broadcast")
    builder.button(text="⚙️ Системные настройки", callback_data="admin_settings")
    builder.button(text="🔙 Выход из админки", callback_data="back_to_main")
    
    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_back_button(callback_data: str) -> InlineKeyboardMarkup:
    """
    Кнопка 'Назад'
    
    Args:
        callback_data: Callback data для кнопки назад
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data=callback_data)
    return builder.as_markup()


def get_home_button() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    return builder.as_markup()


def get_navigation_buttons(
    back_callback: str,
    home: bool = True
) -> InlineKeyboardMarkup:
    """
    Кнопки навигации (назад и домой)
    
    Args:
        back_callback: Callback data для кнопки назад
        home: Добавить кнопку домой
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data=back_callback)
    if home:
        builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    
    builder.adjust(2 if home else 1)
    return builder.as_markup()


def get_confirmation_keyboard(
    yes_callback: str,
    no_callback: str,
    yes_text: str = "✅ Да",
    no_text: str = "❌ Нет"
) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения
    
    Args:
        yes_callback: Callback для подтверждения
        no_callback: Callback для отмены
        yes_text: Текст кнопки подтверждения
        no_text: Текст кнопки отмены
    """
    builder = InlineKeyboardBuilder()
    builder.button(text=yes_text, callback_data=yes_callback)
    builder.button(text=no_text, callback_data=no_callback)
    builder.adjust(2)
    return builder.as_markup()


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """
    Клавиатура пагинации
    
    Args:
        current_page: Текущая страница
        total_pages: Всего страниц
        callback_prefix: Префикс для callback data
    """
    builder = InlineKeyboardBuilder()
    
    # Кнопка "Назад"
    if current_page > 1:
        builder.button(
            text="◀️",
            callback_data=f"{callback_prefix}_page_{current_page - 1}"
        )
    
    # Текущая страница
    builder.button(
        text=f"{current_page}/{total_pages}",
        callback_data=f"{callback_prefix}_page_current"
    )
    
    # Кнопка "Вперед"
    if current_page < total_pages:
        builder.button(
            text="▶️",
            callback_data=f"{callback_prefix}_page_{current_page + 1}"
        )
    
    builder.adjust(3 if current_page > 1 and current_page < total_pages else 2)
    return builder.as_markup()


def get_rating_keyboard(callback_prefix: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для оценки (1-5 звезд)
    
    Args:
        callback_prefix: Префикс для callback data
    """
    builder = InlineKeyboardBuilder()
    
    for i in range(1, 6):
        builder.button(
            text="⭐" * i,
            callback_data=f"{callback_prefix}_rate_{i}"
        )
    
    builder.adjust(1)
    return builder.as_markup()


def get_test_answer_keyboard(
    question_id: int,
    options: List[str]
) -> InlineKeyboardMarkup:
    """
    Клавиатура для ответов на вопросы теста
    
    Args:
        question_id: ID вопроса
        options: Список вариантов ответа
    """
    builder = InlineKeyboardBuilder()
    
    for i, option in enumerate(options):
        builder.button(
            text=f"{chr(65 + i)}. {option}",  # A, B, C, D...
            callback_data=f"test_answer_{question_id}_{i}"
        )
    
    builder.button(text="⏭️ Пропустить", callback_data=f"test_skip_{question_id}")
    builder.adjust(1)
    return builder.as_markup()


def get_share_contact_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура для запроса контакта"""
    builder = InlineKeyboardBuilder()
    
    # Специальная кнопка для запроса контакта
    builder.button(
        text="📱 Поделиться контактом",
        callback_data="share_contact"
    )
    builder.button(text="⏭️ Пропустить", callback_data="skip_contact")
    
    builder.adjust(1)
    return builder.as_markup()

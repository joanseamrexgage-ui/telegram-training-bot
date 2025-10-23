"""
Клавиатуры для раздела "Отдел продаж".

Содержит inline-клавиатуры для:
- Главного меню раздела
- Общей информации (структура, дресс-код, графики)
- Открытия/закрытия парка
- Работы с кассой
- Работы с CRM
- Работы с гостями
- Базы знаний о мошенниках
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_sales_menu() -> InlineKeyboardMarkup:
    """
    Главное меню раздела "Отдел продаж".
    
    Returns:
        InlineKeyboardMarkup с кнопками всех подразделов
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Общая информация",
            callback_data="sales_general"
        )],
        [InlineKeyboardButton(
            text="🏢 Открытие и закрытие парка",
            callback_data="sales_opening"
        )],
        [InlineKeyboardButton(
            text="💳 Работа с кассой",
            callback_data="sales_cash"
        )],
        [InlineKeyboardButton(
            text="📊 Работа с amoCRM",
            callback_data="sales_crm"
        )],
        [InlineKeyboardButton(
            text="🤝 Работа с гостями",
            callback_data="sales_guests"
        )],
        [InlineKeyboardButton(
            text="⚠️ Предупрежден — значит вооружен!",
            callback_data="sales_fraud"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


# ========== ОБЩАЯ ИНФОРМАЦИЯ ==========

def get_sales_general_menu() -> InlineKeyboardMarkup:
    """Меню общей информации об отделе продаж."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👥 Организационная структура",
            callback_data="sales_gen_structure"
        )],
        [InlineKeyboardButton(
            text="👔 Внешний вид сотрудников",
            callback_data="sales_gen_appearance"
        )],
        [InlineKeyboardButton(
            text="⏰ Правила прихода/ухода",
            callback_data="sales_gen_rules"
        )],
        [InlineKeyboardButton(
            text="🌟 Атмосфера в коллективе",
            callback_data="sales_gen_atmosphere"
        )],
        [InlineKeyboardButton(
            text="📅 График работы отдела",
            callback_data="sales_gen_schedule"
        )],
        [InlineKeyboardButton(
            text="💬 Чаты отдела",
            callback_data="sales_gen_chats"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к отделу продаж",
            callback_data="sales"
        )]
    ])
    return keyboard


# ========== ОТКРЫТИЕ/ЗАКРЫТИЕ ==========

def get_opening_closing_menu() -> InlineKeyboardMarkup:
    """Меню открытия и закрытия парка."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="☀️ Открытие парка",
            callback_data="sales_open_park"
        )],
        [InlineKeyboardButton(
            text="🌙 Закрытие парка",
            callback_data="sales_close_park"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к отделу продаж",
            callback_data="sales"
        )]
    ])
    return keyboard


# ========== РАБОТА С КАССОЙ ==========

def get_cash_register_menu() -> InlineKeyboardMarkup:
    """Меню работы с кассой."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎬 Видео-инструкция",
            callback_data="sales_cash_video"
        )],
        [InlineKeyboardButton(
            text="🔌 Включение кассы",
            callback_data="sales_cash_startup"
        )],
        [InlineKeyboardButton(
            text="🎫 Продажа билета",
            callback_data="sales_cash_sale"
        )],
        [InlineKeyboardButton(
            text="↩️ Возврат средств",
            callback_data="sales_cash_refund"
        )],
        [InlineKeyboardButton(
            text="🔐 Закрытие смены",
            callback_data="sales_cash_closing"
        )],
        [InlineKeyboardButton(
            text="❌ Частые ошибки",
            callback_data="sales_cash_errors"
        )],
        [InlineKeyboardButton(
            text="📞 Техподдержка",
            callback_data="sales_cash_support"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к отделу продаж",
            callback_data="sales"
        )]
    ])
    return keyboard


# ========== РАБОТА С CRM ==========

def get_crm_menu() -> InlineKeyboardMarkup:
    """Меню работы с amoCRM."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎬 Видео-инструкция",
            callback_data="sales_crm_video"
        )],
        [InlineKeyboardButton(
            text="🔐 Вход в систему",
            callback_data="sales_crm_login"
        )],
        [InlineKeyboardButton(
            text="➕ Создание сделки",
            callback_data="sales_crm_create"
        )],
        [InlineKeyboardButton(
            text="🎯 Этапы воронки продаж",
            callback_data="sales_crm_funnel"
        )],
        [InlineKeyboardButton(
            text="✅ Работа с задачами",
            callback_data="sales_crm_tasks"
        )],
        [InlineKeyboardButton(
            text="👤 Карточка клиента",
            callback_data="sales_crm_client"
        )],
        [InlineKeyboardButton(
            text="📜 Правила работы в CRM",
            callback_data="sales_crm_rules"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к отделу продаж",
            callback_data="sales"
        )]
    ])
    return keyboard


# ========== РАБОТА С ГОСТЯМИ ==========

def get_guests_menu() -> InlineKeyboardMarkup:
    """Меню работы с гостями."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💬 Скрипты продаж",
            callback_data="sales_guests_scripts"
        )],
        [InlineKeyboardButton(
            text="👶 Работа с детьми и взрослыми",
            callback_data="sales_guests_children"
        )],
        [InlineKeyboardButton(
            text="📱 Сбор контактов для CRM",
            callback_data="sales_guests_contacts"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к отделу продаж",
            callback_data="sales"
        )]
    ])
    return keyboard


def get_sales_scripts_menu() -> InlineKeyboardMarkup:
    """Подменю скриптов продаж."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👋 Приветствие",
            callback_data="sales_script_greeting"
        )],
        [InlineKeyboardButton(
            text="🎯 Выявление потребностей",
            callback_data="sales_script_needs"
        )],
        [InlineKeyboardButton(
            text="🎁 Презентация услуг",
            callback_data="sales_script_presentation"
        )],
        [InlineKeyboardButton(
            text="🛡️ Работа с возражениями",
            callback_data="sales_script_objections"
        )],
        [InlineKeyboardButton(
            text="🎯 Завершение сделки",
            callback_data="sales_script_closing"
        )],
        [InlineKeyboardButton(
            text="📈 Допродажи (Upsell)",
            callback_data="sales_script_upsell"
        )],
        [InlineKeyboardButton(
            text="🔄 Перекрестные продажи",
            callback_data="sales_script_crosssell"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к работе с гостями",
            callback_data="sales_guests"
        )]
    ])
    return keyboard


# ========== БАЗА ЗНАНИЙ О МОШЕННИКАХ ==========

def get_fraud_menu() -> InlineKeyboardMarkup:
    """Меню базы знаний о мошенниках."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💵 Фальшивые купюры",
            callback_data="sales_fraud_money"
        )],
        [InlineKeyboardButton(
            text="↩️ Мошенничество с возвратами",
            callback_data="sales_fraud_refund"
        )],
        [InlineKeyboardButton(
            text="😡 Агрессивные клиенты",
            callback_data="sales_fraud_aggressive"
        )],
        [InlineKeyboardButton(
            text="🕵️ Кража и подозрительное поведение",
            callback_data="sales_fraud_theft"
        )],
        [InlineKeyboardButton(
            text="🚪 Попытки прохода без оплаты",
            callback_data="sales_fraud_freepass"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к отделу продаж",
            callback_data="sales"
        )]
    ])
    return keyboard


# ========== НАВИГАЦИОННЫЕ КНОПКИ ==========

def get_back_to_sales() -> InlineKeyboardMarkup:
    """Простая кнопка возврата к отделу продаж."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Назад к отделу продаж",
            callback_data="sales"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_sales_general() -> InlineKeyboardMarkup:
    """Кнопка возврата к общей информации отдела."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К общей информации",
            callback_data="sales_general"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_opening() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню открытия/закрытия."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К открытию/закрытию",
            callback_data="sales_opening"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_cash() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню кассы."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К работе с кассой",
            callback_data="sales_cash"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_crm() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню CRM."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К работе с CRM",
            callback_data="sales_crm"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_guests() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню работы с гостями."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К работе с гостями",
            callback_data="sales_guests"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_scripts() -> InlineKeyboardMarkup:
    """Кнопка возврата к скриптам продаж."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К скриптам продаж",
            callback_data="sales_guests_scripts"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_fraud() -> InlineKeyboardMarkup:
    """Кнопка возврата к базе знаний о мошенниках."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К базе знаний",
            callback_data="sales_fraud"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard

"""
Клавиатуры для раздела "Спортивный отдел".

Содержит inline-клавиатуры для:
- Главного меню раздела
- Общей информации
- Инструкций по оборудованию
- Правил безопасности
- Действий при травмах
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_sport_menu() -> InlineKeyboardMarkup:
    """Главное меню раздела "Спортивный отдел"."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Общая информация",
            callback_data="sport_general"
        )],
        [InlineKeyboardButton(
            text="⚙️ Инструкции по оборудованию",
            callback_data="sport_equipment"
        )],
        [InlineKeyboardButton(
            text="🛡️ Правила безопасности",
            callback_data="sport_safety"
        )],
        [InlineKeyboardButton(
            text="🏥 Действия при травмах",
            callback_data="sport_injury"
        )],
        [InlineKeyboardButton(
            text="📞 Экстренные контакты",
            callback_data="sport_contacts"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_sport_general_menu() -> InlineKeyboardMarkup:
    """Меню общей информации спортивного отдела."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👥 Организационная структура",
            callback_data="sport_gen_structure"
        )],
        [InlineKeyboardButton(
            text="👔 Внешний вид инструкторов",
            callback_data="sport_gen_appearance"
        )],
        [InlineKeyboardButton(
            text="⏰ Правила работы",
            callback_data="sport_gen_rules"
        )],
        [InlineKeyboardButton(
            text="💪 Физические требования",
            callback_data="sport_gen_physical"
        )],
        [InlineKeyboardButton(
            text="📅 График работы",
            callback_data="sport_gen_schedule"
        )],
        [InlineKeyboardButton(
            text="💬 Чаты отдела",
            callback_data="sport_gen_chats"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к спортивному отделу",
            callback_data="sport"
        )]
    ])
    return keyboard


def get_equipment_menu() -> InlineKeyboardMarkup:
    """Меню инструкций по оборудованию."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🦘 Батуты",
            callback_data="sport_equip_trampoline"
        )],
        [InlineKeyboardButton(
            text="🧗 Скалодром",
            callback_data="sport_equip_climbing"
        )],
        [InlineKeyboardButton(
            text="🌲 Веревочный парк",
            callback_data="sport_equip_rope"
        )],
        [InlineKeyboardButton(
            text="🎮 Игровые автоматы",
            callback_data="sport_equip_games"
        )],
        [InlineKeyboardButton(
            text="🏰 Лабиринт",
            callback_data="sport_equip_labyrinth"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к спортивному отделу",
            callback_data="sport"
        )]
    ])
    return keyboard


def get_safety_menu() -> InlineKeyboardMarkup:
    """Меню правил безопасности."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⚠️ Общие правила безопасности",
            callback_data="sport_safety_general"
        )],
        [InlineKeyboardButton(
            text="🚫 Что запрещено гостям",
            callback_data="sport_safety_prohibited"
        )],
        [InlineKeyboardButton(
            text="👶 Возрастные ограничения",
            callback_data="sport_safety_age"
        )],
        [InlineKeyboardButton(
            text="⚖️ Весовые ограничения",
            callback_data="sport_safety_weight"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к спортивному отделу",
            callback_data="sport"
        )]
    ])
    return keyboard


def get_injury_menu() -> InlineKeyboardMarkup:
    """Меню действий при травмах."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💊 Состав аптечки",
            callback_data="sport_injury_kit"
        )],
        [InlineKeyboardButton(
            text="🩹 Легкие травмы",
            callback_data="sport_injury_minor"
        )],
        [InlineKeyboardButton(
            text="🚑 Серьезные травмы",
            callback_data="sport_injury_serious"
        )],
        [InlineKeyboardButton(
            text="💔 Сердечно-легочная реанимация",
            callback_data="sport_injury_cpr"
        )],
        [InlineKeyboardButton(
            text="🧠 Психологическая помощь",
            callback_data="sport_injury_psych"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к спортивному отделу",
            callback_data="sport"
        )]
    ])
    return keyboard


def get_back_to_sport() -> InlineKeyboardMarkup:
    """Кнопка возврата к спортивному отделу."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Назад к спортивному отделу",
            callback_data="sport"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_sport_general() -> InlineKeyboardMarkup:
    """Кнопка возврата к общей информации."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К общей информации",
            callback_data="sport_general"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_equipment() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню оборудования."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К списку оборудования",
            callback_data="sport_equipment"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_safety() -> InlineKeyboardMarkup:
    """Кнопка возврата к правилам безопасности."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К правилам безопасности",
            callback_data="sport_safety"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_injury() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню травм."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К действиям при травмах",
            callback_data="sport_injury"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard

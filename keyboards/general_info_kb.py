"""
Клавиатуры для раздела "Общая информация".

Содержит inline-клавиатуры для:
- Главного меню раздела
- Выбора парков (адреса, телефоны)
- Подразделов (внештатные ситуации, зарплата, приказы, скидки)
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_general_info_menu() -> InlineKeyboardMarkup:
    """
    Главное меню раздела "Общая информация".
    
    Returns:
        InlineKeyboardMarkup с кнопками всех подразделов
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📍 Адреса парков",
            callback_data="gen_addresses"
        )],
        [InlineKeyboardButton(
            text="📞 Важные номера телефонов",
            callback_data="gen_phones"
        )],
        [InlineKeyboardButton(
            text="🚨 Действия во внештатных ситуациях",
            callback_data="gen_emergency"
        )],
        [InlineKeyboardButton(
            text="💰 Аванс и зарплата",
            callback_data="gen_salary"
        )],
        [InlineKeyboardButton(
            text="📄 Все приказы парка",
            callback_data="gen_orders"
        )],
        [InlineKeyboardButton(
            text="🎁 Скидки у партнеров ТРЦ",
            callback_data="gen_discounts"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_parks_menu() -> InlineKeyboardMarkup:
    """
    DEPRECATED: Используйте get_parks_addresses_menu() или get_parks_phones_menu().

    Меню выбора парка (для адресов и телефонов).

    Returns:
        InlineKeyboardMarkup с кнопками трех парков
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏢 ТРЦ Зеленопарк",
            callback_data="park_zeleno"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Каширская плаза",
            callback_data="park_kashir"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Коламбус",
            callback_data="park_columb"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="general_info"
        )]
    ])
    return keyboard


def get_parks_addresses_menu() -> InlineKeyboardMarkup:
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Отдельное меню для адресов парков.

    Проблема: Ранее одна клавиатура get_parks_menu() использовалась и для адресов,
    и для телефонов, из-за чего обработчики конфликтовали.

    Returns:
        InlineKeyboardMarkup с кнопками трех парков для просмотра адресов
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏢 ТРЦ Зеленопарк",
            callback_data="addr_zeleno"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Каширская плаза",
            callback_data="addr_kashir"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Коламбус",
            callback_data="addr_columb"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="general_info"
        )]
    ])
    return keyboard


def get_parks_phones_menu() -> InlineKeyboardMarkup:
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Отдельное меню для телефонов парков.

    Проблема: Ранее одна клавиатура get_parks_menu() использовалась и для адресов,
    и для телефонов, из-за чего при нажатии на парк в разделе "Важные номера"
    показывался адрес, а не телефоны.

    Returns:
        InlineKeyboardMarkup с кнопками трех парков для просмотра телефонов
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏢 ТРЦ Зеленопарк",
            callback_data="phone_zeleno"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Каширская плаза",
            callback_data="phone_kashir"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Коламбус",
            callback_data="phone_columb"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="general_info"
        )]
    ])
    return keyboard


def get_emergency_menu() -> InlineKeyboardMarkup:
    """
    Меню внештатных ситуаций.
    
    Returns:
        InlineKeyboardMarkup с типами чрезвычайных ситуаций
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔥 Эвакуация",
            callback_data="emergency_evacuation"
        )],
        [InlineKeyboardButton(
            text="🔥 Пожар",
            callback_data="emergency_fire"
        )],
        [InlineKeyboardButton(
            text="⚕️ Медицинский случай",
            callback_data="emergency_medical"
        )],
        [InlineKeyboardButton(
            text="😡 Конфликт с гостем",
            callback_data="emergency_conflict"
        )],
        [InlineKeyboardButton(
            text="⚙️ Техническая поломка",
            callback_data="emergency_technical"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="general_info"
        )]
    ])
    return keyboard


def get_orders_menu() -> InlineKeyboardMarkup:
    """
    Меню приказов парка.
    
    Returns:
        InlineKeyboardMarkup со списком приказов (пример)
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📄 Приказ №1 - О внутреннем распорядке",
            callback_data="order_001"
        )],
        [InlineKeyboardButton(
            text="📄 Приказ №2 - О дресс-коде",
            callback_data="order_002"
        )],
        [InlineKeyboardButton(
            text="📄 Приказ №3 - О правилах безопасности",
            callback_data="order_003"
        )],
        [InlineKeyboardButton(
            text="📄 Приказ №4 - О порядке выдачи зарплаты",
            callback_data="order_004"
        )],
        [InlineKeyboardButton(
            text="📄 Приказ №5 - О корпоративной этике",
            callback_data="order_005"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="general_info"
        )]
    ])
    return keyboard


def get_discounts_parks_menu() -> InlineKeyboardMarkup:
    """
    Меню выбора парка для просмотра скидок партнеров.
    
    Returns:
        InlineKeyboardMarkup с кнопками трех парков
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏢 ТРЦ Зеленопарк",
            callback_data="discount_zeleno"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Каширская плаза",
            callback_data="discount_kashir"
        )],
        [InlineKeyboardButton(
            text="🏢 ТРЦ Коламбус",
            callback_data="discount_columb"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="general_info"
        )]
    ])
    return keyboard


def get_back_to_general_info() -> InlineKeyboardMarkup:
    """
    Простая кнопка "Назад" в общую информацию.
    
    Returns:
        InlineKeyboardMarkup с одной кнопкой назад
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data="general_info"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_park_address_detail_keyboard(park_code: str) -> InlineKeyboardMarkup:
    """
    Клавиатура для детального просмотра адреса парка с навигацией.

    Args:
        park_code: Код парка (zeleno, kashir, columb)

    Returns:
        InlineKeyboardMarkup с кнопками навигации по парку, назад и домой
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🗺️ Навигация по парку",
            callback_data=f"nav_{park_code}"
        )],
        [InlineKeyboardButton(
            text="◀️ К списку парков",
            callback_data="gen_addresses"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_addresses() -> InlineKeyboardMarkup:
    """
    Кнопка возврата к списку адресов.

    Returns:
        InlineKeyboardMarkup с кнопкой назад к адресам
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К списку парков",
            callback_data="gen_addresses"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_phones() -> InlineKeyboardMarkup:
    """
    Кнопка возврата к списку телефонов.
    
    Returns:
        InlineKeyboardMarkup с кнопкой назад к телефонам
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К списку парков",
            callback_data="gen_phones"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_emergency() -> InlineKeyboardMarkup:
    """
    Кнопка возврата к списку внештатных ситуаций.
    
    Returns:
        InlineKeyboardMarkup с кнопкой назад к меню ЧС
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К списку ситуаций",
            callback_data="gen_emergency"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_back_to_discounts() -> InlineKeyboardMarkup:
    """
    Кнопка возврата к выбору парка для скидок.
    
    Returns:
        InlineKeyboardMarkup с кнопкой назад к выбору парка
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ К списку парков",
            callback_data="gen_discounts"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard

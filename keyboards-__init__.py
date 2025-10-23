"""
Пакет клавиатур для Telegram-бота.

Содержит inline-клавиатуры для:
- inline.py: Главное меню и общие кнопки
- general_info_kb.py: Клавиатуры раздела "Общая информация"
- sales_kb.py: Клавиатуры раздела "Отдел продаж"
- sport_kb.py: Клавиатуры раздела "Спортивный отдел"
- admin_kb.py: Клавиатуры админ-панели
"""

from keyboards.inline import (
    get_main_menu_keyboard,
    get_home_button,
)

from keyboards.general_info_kb import (
    get_general_info_menu,
    get_parks_menu,
    get_emergency_menu,
    get_orders_menu,
    get_discounts_parks_menu,
    get_back_to_general_info,
)

from keyboards.sales_kb import (
    get_sales_menu,
    get_sales_general_menu,
    get_opening_closing_menu,
    get_cash_register_menu,
    get_crm_menu,
    get_guests_menu,
    get_sales_scripts_menu,
    get_fraud_menu,
    get_back_to_sales,
)

from keyboards.sport_kb import (
    get_sport_menu,
    get_sport_general_menu,
    get_equipment_menu,
    get_safety_menu,
    get_injury_menu,
    get_back_to_sport,
)

from keyboards.admin_kb import (
    get_admin_menu,
    get_admin_users_menu,
    get_admin_stats_menu,
    get_admin_broadcast_menu,
    get_admin_content_menu,
)

__all__ = [
    # Главное меню
    'get_main_menu_keyboard',
    'get_home_button',
    # Общая информация
    'get_general_info_menu',
    'get_parks_menu',
    'get_emergency_menu',
    'get_orders_menu',
    'get_discounts_parks_menu',
    'get_back_to_general_info',
    # Отдел продаж
    'get_sales_menu',
    'get_sales_general_menu',
    'get_opening_closing_menu',
    'get_cash_register_menu',
    'get_crm_menu',
    'get_guests_menu',
    'get_sales_scripts_menu',
    'get_fraud_menu',
    'get_back_to_sales',
    # Спортивный отдел
    'get_sport_menu',
    'get_sport_general_menu',
    'get_equipment_menu',
    'get_safety_menu',
    'get_injury_menu',
    'get_back_to_sport',
    # Админ-панель
    'get_admin_menu',
    'get_admin_users_menu',
    'get_admin_stats_menu',
    'get_admin_broadcast_menu',
    'get_admin_content_menu',
]
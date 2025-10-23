"""
Клавиатуры для админ-панели.

Содержит inline-клавиатуры для:
- Главного меню админки
- Управления контентом
- Статистики
- Управления пользователями
- Рассылки сообщений
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_admin_main_menu() -> InlineKeyboardMarkup:
    """Главное меню админ-панели."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Статистика использования",
            callback_data="admin_stats"
        )],
        [InlineKeyboardButton(
            text="👥 Управление пользователями",
            callback_data="admin_users"
        )],
        [InlineKeyboardButton(
            text="✏️ Редактировать контент",
            callback_data="admin_content"
        )],
        [InlineKeyboardButton(
            text="📢 Рассылка сообщений",
            callback_data="admin_broadcast"
        )],
        [InlineKeyboardButton(
            text="📋 Логи активности",
            callback_data="admin_logs"
        )],
        [InlineKeyboardButton(
            text="🚪 Выйти из админки",
            callback_data="admin_logout"
        )]
    ])
    return keyboard


def get_stats_menu() -> InlineKeyboardMarkup:
    """Меню статистики."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📈 Общая статистика",
            callback_data="stats_general"
        )],
        [InlineKeyboardButton(
            text="👤 Статистика пользователей",
            callback_data="stats_users"
        )],
        [InlineKeyboardButton(
            text="📱 Популярные разделы",
            callback_data="stats_sections"
        )],
        [InlineKeyboardButton(
            text="📅 Статистика по датам",
            callback_data="stats_dates"
        )],
        [InlineKeyboardButton(
            text="📊 Экспорт в Excel",
            callback_data="stats_export"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к админке",
            callback_data="admin_panel"
        )]
    ])
    return keyboard


def get_users_menu() -> InlineKeyboardMarkup:
    """Меню управления пользователями."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Список всех пользователей",
            callback_data="users_list"
        )],
        [InlineKeyboardButton(
            text="🔍 Поиск пользователя",
            callback_data="users_search"
        )],
        [InlineKeyboardButton(
            text="🚫 Заблокированные",
            callback_data="users_blocked"
        )],
        [InlineKeyboardButton(
            text="✅ Активные сегодня",
            callback_data="users_active"
        )],
        [InlineKeyboardButton(
            text="🆕 Новые пользователи",
            callback_data="users_new"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к админке",
            callback_data="admin_panel"
        )]
    ])
    return keyboard


def get_user_actions(user_id: int, is_blocked: bool = False) -> InlineKeyboardMarkup:
    """Клавиатура действий с конкретным пользователем."""
    block_text = "✅ Разблокировать" if is_blocked else "🚫 Заблокировать"
    block_action = f"user_unblock_{user_id}" if is_blocked else f"user_block_{user_id}"
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📊 Статистика пользователя",
            callback_data=f"user_stats_{user_id}"
        )],
        [InlineKeyboardButton(
            text=block_text,
            callback_data=block_action
        )],
        [InlineKeyboardButton(
            text="📨 Отправить сообщение",
            callback_data=f"user_message_{user_id}"
        )],
        [InlineKeyboardButton(
            text="◀️ К списку пользователей",
            callback_data="users_list"
        )]
    ])
    return keyboard


def get_content_menu() -> InlineKeyboardMarkup:
    """Меню управления контентом."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🟢 Общая информация",
            callback_data="content_general"
        )],
        [InlineKeyboardButton(
            text="🔴 Отдел продаж",
            callback_data="content_sales"
        )],
        [InlineKeyboardButton(
            text="🟡 Спортивный отдел",
            callback_data="content_sport"
        )],
        [InlineKeyboardButton(
            text="📹 Загрузить видео",
            callback_data="content_upload_video"
        )],
        [InlineKeyboardButton(
            text="📄 Загрузить документ",
            callback_data="content_upload_doc"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к админке",
            callback_data="admin_panel"
        )]
    ])
    return keyboard


def get_content_section_menu(section: str) -> InlineKeyboardMarkup:
    """Меню редактирования конкретного раздела."""
    sections_data = {
        "general": [
            ("📍 Адреса парков", "general_addresses"),
            ("📞 Телефоны", "general_phones"),
            ("⚠️ Внештатные ситуации", "general_emergency"),
            ("💰 Зарплата", "general_salary"),
            ("📋 Приказы", "general_orders"),
            ("🎁 Скидки", "general_discounts"),
        ],
        "sales": [
            ("👥 Общая информация", "sales_general"),
            ("🏪 Открытие/закрытие", "sales_opening"),
            ("💳 Работа с кассой", "sales_cash"),
            ("📊 Работа с CRM", "sales_crm"),
            ("🤝 Работа с гостями", "sales_guests"),
            ("⚠️ Мошенники", "sales_scammers"),
        ],
        "sport": [
            ("👥 Общая информация", "sport_general"),
            ("⚙️ Оборудование", "sport_equipment"),
            ("🛡️ Безопасность", "sport_safety"),
            ("🏥 Травмы", "sport_injury"),
        ]
    }
    
    buttons = []
    for title, callback in sections_data.get(section, []):
        buttons.append([InlineKeyboardButton(
            text=title,
            callback_data=f"edit_{callback}"
        )])
    
    buttons.append([InlineKeyboardButton(
        text="◀️ К управлению контентом",
        callback_data="admin_content"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


def get_broadcast_menu() -> InlineKeyboardMarkup:
    """Меню рассылки."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📢 Всем пользователям",
            callback_data="broadcast_all"
        )],
        [InlineKeyboardButton(
            text="🔴 Только отделу продаж",
            callback_data="broadcast_sales"
        )],
        [InlineKeyboardButton(
            text="🟡 Только спортивному отделу",
            callback_data="broadcast_sport"
        )],
        [InlineKeyboardButton(
            text="✅ Только активным",
            callback_data="broadcast_active"
        )],
        [InlineKeyboardButton(
            text="📋 История рассылок",
            callback_data="broadcast_history"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад к админке",
            callback_data="admin_panel"
        )]
    ])
    return keyboard


def get_broadcast_confirm(target: str, count: int) -> InlineKeyboardMarkup:
    """Подтверждение рассылки."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"✅ Отправить ({count} чел.)",
            callback_data=f"broadcast_send_{target}"
        )],
        [InlineKeyboardButton(
            text="❌ Отменить",
            callback_data="admin_broadcast"
        )]
    ])
    return keyboard


def get_back_to_admin() -> InlineKeyboardMarkup:
    """Кнопка возврата в админку."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Назад к админке",
            callback_data="admin_panel"
        )],
        [InlineKeyboardButton(
            text="🏠 Главное меню",
            callback_data="main_menu"
        )]
    ])
    return keyboard


def get_cancel_button() -> InlineKeyboardMarkup:
    """
    Кнопка отмены текущей операции.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Ранее использовался callback_data="admin_panel",
    что вызывало ошибку при отмене ввода пароля, т.к. обработчик admin_panel
    проверяет авторизацию и отказывает в доступе неавторизованным пользователям.

    Теперь используется уникальный callback_data="cancel_admin_action" с отдельным
    обработчиком, который корректно сбрасывает FSM и возвращает в главное меню.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚫 Отменить",
            callback_data="cancel_admin_action"
        )]
    ])
    return keyboard


def get_edit_actions(section: str, key: str) -> InlineKeyboardMarkup:
    """Действия для редактирования контента."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✏️ Изменить текст",
            callback_data=f"edit_text_{section}_{key}"
        )],
        [InlineKeyboardButton(
            text="📹 Заменить видео",
            callback_data=f"edit_video_{section}_{key}"
        )],
        [InlineKeyboardButton(
            text="📄 Заменить документ",
            callback_data=f"edit_doc_{section}_{key}"
        )],
        [InlineKeyboardButton(
            text="🗑️ Удалить",
            callback_data=f"edit_delete_{section}_{key}"
        )],
        [InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"content_{section}"
        )]
    ])
    return keyboard


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str
) -> InlineKeyboardMarkup:
    """Клавиатура пагинации для списков."""
    buttons = []
    
    # Навигация
    nav_row = []
    if current_page > 1:
        nav_row.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"{callback_prefix}_page_{current_page - 1}"
        ))
    
    nav_row.append(InlineKeyboardButton(
        text=f"📄 {current_page}/{total_pages}",
        callback_data="page_info"
    ))
    
    if current_page < total_pages:
        nav_row.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"{callback_prefix}_page_{current_page + 1}"
        ))
    
    buttons.append(nav_row)
    
    # Кнопка возврата
    buttons.append([InlineKeyboardButton(
        text="◀️ Назад к админке",
        callback_data="admin_panel"
    )])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard

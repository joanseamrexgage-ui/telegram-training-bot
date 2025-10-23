"""
FSM состояния для админ-панели.

Содержит состояния для:
- Авторизации администратора
- Управления контентом
- Просмотра статистики
- Управления пользователями
- Рассылки сообщений
"""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """Состояния для работы с админ-панелью."""
    
    # Авторизация
    waiting_for_password = State()  # Ожидание ввода пароля
    authorized = State()  # Авторизован (в главном меню админки)
    
    # Управление контентом
    content_management = State()  # В меню управления контентом
    content_select_section = State()  # Выбор раздела для редактирования
    content_editing = State()  # Редактирование контента
    content_waiting_file = State()  # Ожидание загрузки файла (видео/документа)
    
    # Статистика
    stats_menu = State()  # В меню статистики
    stats_viewing = State()  # Просмотр детальной статистики
    
    # Управление пользователями
    users_menu = State()  # Меню управления пользователями
    users_viewing = State()  # Просмотр списка пользователей
    users_blocking = State()  # Блокировка пользователя
    users_waiting_id = State()  # Ожидание ID пользователя
    
    # Рассылка
    broadcast_menu = State()  # Меню рассылки
    broadcast_waiting_text = State()  # Ожидание текста для рассылки
    broadcast_select_target = State()  # Выбор целевой аудитории
    broadcast_confirm = State()  # Подтверждение рассылки
    broadcast_sending = State()  # Процесс отправки


class ContentEditStates(StatesGroup):
    """Состояния для редактирования контента."""
    
    waiting_new_text = State()  # Ожидание нового текста
    waiting_video = State()  # Ожидание видео
    waiting_document = State()  # Ожидание документа
    waiting_image = State()  # Ожидание изображения
    confirm_changes = State()  # Подтверждение изменений

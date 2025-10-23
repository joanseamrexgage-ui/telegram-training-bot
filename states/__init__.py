"""
Пакет состояний FSM (Finite State Machine) для Telegram-бота.

Содержит классы состояний для:
- menu_states.py: Состояния главного меню и разделов
- admin_states.py: Состояния админ-панели
"""

from aiogram.fsm.state import State, StatesGroup

# Импортируем состояния меню
from states.menu_states import MenuStates

# Импортируем состояния админ-панели
from states.admin_states import AdminStates, ContentEditStates

__all__ = [
    'State',
    'StatesGroup',
    'MenuStates',
    'AdminStates',
    'ContentEditStates',
]
"""
Пакет обработчиков команд и callback-запросов Telegram-бота.

Содержит роутеры для:
- start.py: Команда /start и главное меню
- general_info.py: Раздел "Общая информация"
- sales.py: Раздел "Отдел продаж"
- sport.py: Раздел "Спортивный отдел"
- admin.py: Раздел "Администрация парка"
"""

from aiogram import Router

# Импортируем все роутеры
from handlers.start import router as start_router
from handlers.general_info import router as general_info_router
from handlers.sales import router as sales_router
from handlers.sport import router as sport_router
from handlers.admin import router as admin_router

# Список всех роутеров для регистрации в диспетчере
routers = [
    start_router,
    general_info_router,
    sales_router,
    sport_router,
    admin_router,
]

__all__ = [
    'start_router',
    'general_info_router',
    'sales_router',
    'sport_router',
    'admin_router',
    'routers',
]
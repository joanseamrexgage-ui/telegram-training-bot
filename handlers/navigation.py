"""
Handler для раздела "Навигация".

Обрабатывает все callback'ы связанные с навигацией по паркам:
- Выбор парка
- Просмотр зон и ориентиров
- Важные локации (выходы, огнетушители, туалеты)
"""

import json
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from states.menu_states import MenuStates
from utils.logger import logger

# Создаем router для этого модуля
router = Router(name='navigation')

# Загружаем контент из JSON
CONTENT_PATH = Path(__file__).parent.parent / "content" / "texts" / "navigation.json"

try:
    with open(CONTENT_PATH, 'r', encoding='utf-8') as f:
        CONTENT = json.load(f)
    logger.info("✅ Контент navigation.json загружен успешно")
except FileNotFoundError:
    logger.error(f"❌ Файл {CONTENT_PATH} не найден!")
    CONTENT = {}
except json.JSONDecodeError as e:
    logger.error(f"❌ Ошибка парсинга JSON: {e}")
    CONTENT = {}


def get_navigation_menu() -> InlineKeyboardMarkup:
    """Меню выбора парка для навигации"""
    builder = InlineKeyboardBuilder()

    builder.button(text="🏢 ТРЦ Каширская плаза", callback_data="nav_kashirskaya")
    builder.button(text="🏢 ТРЦ Коламбус", callback_data="nav_columbus")
    builder.button(text="🏢 ТРЦ Зеленопарк", callback_data="nav_zeleno")
    builder.button(text="◀️ Назад", callback_data="back_to_main")

    builder.adjust(1)
    return builder.as_markup()


def get_back_to_navigation() -> InlineKeyboardMarkup:
    """Кнопка возврата к выбору парка"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="navigation")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data == "navigation")
async def show_navigation_menu(callback: CallbackQuery, state: FSMContext):
    """
    Показывает главное меню раздела "Навигация".

    Args:
        callback: Callback от нажатия кнопки
        state: FSM контекст
    """
    await state.set_state(MenuStates.main_menu)

    main_menu_text = CONTENT.get("main_menu", {})
    text = (
        f"<b>{main_menu_text.get('title', '🗺️ Навигация')}</b>\n\n"
        f"{main_menu_text.get('description', 'Выберите парк для просмотра навигации:')}"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_navigation_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_navigation_menu: {e}")
        await callback.answer("Произошла ошибка. Попробуйте еще раз.")


@router.callback_query(F.data.startswith("nav_"))
async def show_park_navigation(callback: CallbackQuery):
    """
    Показывает навигацию для конкретного парка.

    Обрабатывает callback: nav_kashirskaya, nav_columbus, nav_zeleno
    """
    park_code = callback.data.split("_")[1]  # kashirskaya, columbus, zeleno
    logger.info(f"🗺️ Пользователь {callback.from_user.id} запрашивает навигацию парка '{park_code}'")

    park_info = CONTENT.get(park_code, {})

    if not park_info:
        logger.warning(f"⚠️ Информация о навигации парка '{park_code}' не найдена")
        await callback.answer(
            "Информация о навигации для выбранного парка временно недоступна.",
            show_alert=True
        )
        return

    # Формируем текст с информацией о парке
    text = f"<b>🗺️ {park_info.get('name')}</b>\n\n"
    text += f"<b>📍 Расположение:</b> {park_info.get('floor')}, {park_info.get('location')}\n\n"

    # Добавляем навигацию от входа (если есть)
    if "navigation_from_entrance" in park_info:
        text += "<b>🚶 Как найти парк:</b>\n"
        for step in park_info["navigation_from_entrance"]:
            text += f"{step}\n"
        text += "\n"

    # Добавляем зоны
    text += "<b>🏢 Зоны парка:</b>\n\n"
    for zone in park_info.get("zones", []):
        text += f"<b>{zone['name']}</b>\n"
        text += f"• {zone['description']}\n"
        text += f"• {zone['landmarks']}\n\n"

    # Добавляем важные заметки
    if "important_notes" in park_info:
        text += "<b>⚠️ Важные ориентиры:</b>\n"
        for note in park_info["important_notes"]:
            text += f"{note}\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_navigation()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_park_navigation: {e}")
        await callback.answer("Ошибка загрузки навигации")

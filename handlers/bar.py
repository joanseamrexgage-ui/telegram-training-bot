"""
Handler для раздела "БАР".

Обрабатывает все callback'ы связанные с баром:
- Меню напитков
- Цены и категории
- Рецепты и стандарты приготовления
- Скидки для сотрудников
- Правила обслуживания
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
router = Router(name='bar')

# Загружаем контент из JSON
CONTENT_PATH = Path(__file__).parent.parent / "content" / "texts" / "bar_menu.json"

try:
    with open(CONTENT_PATH, 'r', encoding='utf-8') as f:
        CONTENT = json.load(f)
    logger.info("✅ Контент bar_menu.json загружен успешно")
except FileNotFoundError:
    logger.error(f"❌ Файл {CONTENT_PATH} не найден!")
    CONTENT = {}
except json.JSONDecodeError as e:
    logger.error(f"❌ Ошибка парсинга JSON: {e}")
    CONTENT = {}


def get_bar_menu() -> InlineKeyboardMarkup:
    """Меню раздела БАР"""
    builder = InlineKeyboardBuilder()

    builder.button(text="🍹 Меню напитков", callback_data="bar_drinks")
    builder.button(text="💼 Скидки для сотрудников", callback_data="bar_discount")
    builder.button(text="📋 Стандарты приготовления", callback_data="bar_standards")
    builder.button(text="🎯 Правила обслуживания", callback_data="bar_service")
    builder.button(text="◀️ Назад", callback_data="back_to_main")

    builder.adjust(1)
    return builder.as_markup()


def get_drinks_category_menu() -> InlineKeyboardMarkup:
    """Меню выбора категории напитков"""
    builder = InlineKeyboardBuilder()

    builder.button(text="☕ Горячие напитки", callback_data="bar_drinks_hot")
    builder.button(text="🧊 Холодные напитки", callback_data="bar_drinks_cold")
    builder.button(text="🍋 Лимонады", callback_data="bar_drinks_lemonade")
    builder.button(text="🥤 Милкшейки и смузи", callback_data="bar_drinks_milkshake")
    builder.button(text="◀️ Назад", callback_data="bar")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")

    builder.adjust(1, 1, 1, 1, 2)
    return builder.as_markup()


def get_back_to_bar() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню БАР"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="bar")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()


def get_back_to_drinks() -> InlineKeyboardMarkup:
    """Кнопка возврата к категориям напитков"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="bar_drinks")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data == "bar")
async def show_bar_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает главное меню раздела БАР"""
    await state.set_state(MenuStates.main_menu)

    main_menu_text = CONTENT.get("main_menu", {})
    text = (
        f"<b>{main_menu_text.get('title', '☕ БАР')}</b>\n\n"
        f"{main_menu_text.get('description', 'Выберите раздел:')}"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_bar_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_bar_menu: {e}")
        await callback.answer("Произошла ошибка. Попробуйте еще раз.")


@router.callback_query(F.data == "bar_drinks")
async def show_drinks_categories(callback: CallbackQuery):
    """Показывает категории напитков"""
    text = (
        "<b>🍹 Меню напитков</b>\n\n"
        "Выберите категорию для просмотра меню:"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_drinks_category_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_drinks_categories: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("bar_drinks_"))
async def show_drinks_by_category(callback: CallbackQuery):
    """Показывает напитки по категории"""
    category_code = callback.data.replace("bar_drinks_", "")  # hot, cold, lemonade, milkshake

    category_map = {
        "hot": "☕ Горячие напитки",
        "cold": "🧊 Холодные напитки",
        "lemonade": "🍋 Лимонады",
        "milkshake": "🥤 Милкшейки и смузи"
    }

    drinks_data = CONTENT.get("drinks", {})
    categories = drinks_data.get("categories", [])

    # Находим нужную категорию
    category = None
    for cat in categories:
        if category_map.get(category_code) == cat["name"]:
            category = cat
            break

    if not category:
        await callback.answer("Категория не найдена", show_alert=True)
        return

    text = f"<b>{category['name']}</b>\n\n"

    for item in category["items"]:
        text += f"<b>{item['name']}</b> — {item['price']}\n"
        text += f"• {item['volume']}\n"
        text += f"• {item['description']}\n\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_drinks()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_drinks_by_category: {e}")
        await callback.answer("Ошибка загрузки напитков")


@router.callback_query(F.data == "bar_discount")
async def show_employee_discount(callback: CallbackQuery):
    """Показывает информацию о скидках для сотрудников"""
    discount_data = CONTENT.get("employee_discount", {})

    text = f"<b>{discount_data.get('title', '💼 Скидка для сотрудников')}</b>\n\n"
    text += f"{discount_data.get('description', '')}\n\n"

    for benefit in discount_data.get("benefits", []):
        text += f"{benefit}\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_bar()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_employee_discount: {e}")
        await callback.answer("Ошибка загрузки информации")


@router.callback_query(F.data == "bar_standards")
async def show_preparation_standards(callback: CallbackQuery):
    """Показывает стандарты приготовления напитков"""
    standards_data = CONTENT.get("standards", {})

    text = f"<b>{standards_data.get('title', '📋 Стандарты приготовления')}</b>\n\n"
    text += f"{standards_data.get('description', '')}\n\n"

    recipes = standards_data.get("recipes", [])
    for recipe in recipes[:2]:  # Показываем первые 2 рецепта для экономии места
        text += f"<b>{recipe['drink']}</b>\n"
        for step in recipe["steps"]:
            text += f"{step}\n"
        text += f"⏱️ Время: {recipe['time']}\n"
        text += f"🌡️ Температура: {recipe['temperature']}\n\n"

    text += "<b>✅ Контроль качества:</b>\n"
    for check in standards_data.get("quality_check", []):
        text += f"{check}\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_bar()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_preparation_standards: {e}")
        await callback.answer("Ошибка загрузки стандартов")


@router.callback_query(F.data == "bar_service")
async def show_service_rules(callback: CallbackQuery):
    """Показывает правила обслуживания"""
    service_data = CONTENT.get("service_rules", {})

    text = f"<b>{service_data.get('title', '🎯 Правила обслуживания')}</b>\n\n"

    for step in service_data.get("steps", []):
        text += f"{step}\n"

    text += "\n<b>💡 Полезные советы:</b>\n"
    for tip in service_data.get("tips", []):
        text += f"{tip}\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_bar()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_service_rules: {e}")
        await callback.answer("Ошибка загрузки правил")

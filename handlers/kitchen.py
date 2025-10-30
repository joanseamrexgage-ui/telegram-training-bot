"""
Handler для раздела "Наша кухня".

Обрабатывает все callback'ы связанные с кухней:
- Меню блюд по категориям
- Информация об аллергенах
- Технологические карты
- Скидки для сотрудников
- Правила гигиены
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
router = Router(name='kitchen')

# Загружаем контент из JSON
CONTENT_PATH = Path(__file__).parent.parent / "content" / "texts" / "kitchen_menu.json"

try:
    with open(CONTENT_PATH, 'r', encoding='utf-8') as f:
        CONTENT = json.load(f)
    logger.info("✅ Контент kitchen_menu.json загружен успешно")
except FileNotFoundError:
    logger.error(f"❌ Файл {CONTENT_PATH} не найден!")
    CONTENT = {}
except json.JSONDecodeError as e:
    logger.error(f"❌ Ошибка парсинга JSON: {e}")
    CONTENT = {}


def get_kitchen_menu() -> InlineKeyboardMarkup:
    """Меню раздела Наша кухня"""
    builder = InlineKeyboardBuilder()

    builder.button(text="📋 Меню блюд", callback_data="kitchen_menu")
    builder.button(text="⚠️ Информация об аллергенах", callback_data="kitchen_allergens")
    builder.button(text="📋 Технологические карты", callback_data="kitchen_tech_cards")
    builder.button(text="💼 Скидки для сотрудников", callback_data="kitchen_discount")
    builder.button(text="🧼 Правила гигиены", callback_data="kitchen_hygiene")
    builder.button(text="◀️ Назад", callback_data="back_to_main")

    builder.adjust(1)
    return builder.as_markup()


def get_menu_categories() -> InlineKeyboardMarkup:
    """Меню выбора категории блюд"""
    builder = InlineKeyboardBuilder()

    builder.button(text="🍕 Пицца", callback_data="kitchen_cat_pizza")
    builder.button(text="🍔 Бургеры и сэндвичи", callback_data="kitchen_cat_burgers")
    builder.button(text="🍟 Закуски", callback_data="kitchen_cat_snacks")
    builder.button(text="🥗 Салаты", callback_data="kitchen_cat_salads")
    builder.button(text="🍰 Десерты", callback_data="kitchen_cat_desserts")
    builder.button(text="◀️ Назад", callback_data="kitchen")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")

    builder.adjust(1, 1, 1, 1, 1, 2)
    return builder.as_markup()


def get_back_to_kitchen() -> InlineKeyboardMarkup:
    """Кнопка возврата к меню кухни"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="kitchen")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()


def get_back_to_menu() -> InlineKeyboardMarkup:
    """Кнопка возврата к категориям меню"""
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="kitchen_menu")
    builder.button(text="🏠 Главное меню", callback_data="back_to_main")
    builder.adjust(2)
    return builder.as_markup()


@router.callback_query(F.data == "kitchen")
async def show_kitchen_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает главное меню раздела Наша кухня"""
    await state.set_state(MenuStates.main_menu)

    main_menu_text = CONTENT.get("main_menu", {})
    text = (
        f"<b>{main_menu_text.get('title', '🍽️ Наша кухня')}</b>\n\n"
        f"{main_menu_text.get('description', 'Выберите раздел:')}"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_kitchen_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_kitchen_menu: {e}")
        await callback.answer("Произошла ошибка. Попробуйте еще раз.")


@router.callback_query(F.data == "kitchen_menu")
async def show_menu_categories_handler(callback: CallbackQuery):
    """Показывает категории блюд"""
    text = (
        "<b>📋 Меню блюд</b>\n\n"
        "Выберите категорию для просмотра меню:"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_menu_categories()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_menu_categories: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("kitchen_cat_"))
async def show_menu_by_category(callback: CallbackQuery):
    """Показывает блюда по категории"""
    category_code = callback.data.replace("kitchen_cat_", "")

    category_map = {
        "pizza": "🍕 Пицца",
        "burgers": "🍔 Бургеры и сэндвичи",
        "snacks": "🍟 Закуски",
        "salads": "🥗 Салаты",
        "desserts": "🍰 Десерты"
    }

    menu_data = CONTENT.get("menu", {})
    categories = menu_data.get("categories", [])

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
        text += f"• Вес: {item['weight']}\n"
        text += f"• {item['description']}\n"

        if item.get("allergens"):
            allergens_str = ", ".join(item["allergens"])
            text += f"⚠️ Аллергены: {allergens_str}\n"

        text += "\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_menu_by_category: {e}")
        await callback.answer("Ошибка загрузки блюд")


@router.callback_query(F.data == "kitchen_allergens")
async def show_allergens_info(callback: CallbackQuery):
    """Показывает информацию об аллергенах"""
    allergens_data = CONTENT.get("allergens", {})

    text = f"<b>{allergens_data.get('title', '⚠️ Информация об аллергенах')}</b>\n\n"
    text += f"{allergens_data.get('description', '')}\n\n"

    text += "<b>Основные аллергены:</b>\n\n"
    for allergen in allergens_data.get("common_allergens", [])[:4]:  # Первые 4 для экономии места
        text += f"<b>{allergen['name']}</b>\n"
        text += f"• Источники: {allergen['sources']}\n"
        text += f"• {allergen['severity']}\n\n"

    text += "<b>Протокол действий:</b>\n\n"
    for action in allergens_data.get("action_protocol", [])[:6]:  # Первые 6 шагов
        text += f"{action}\n"

    text += f"\n{allergens_data.get('important', '')}"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_kitchen()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_allergens_info: {e}")
        await callback.answer("Ошибка загрузки информации")


@router.callback_query(F.data == "kitchen_tech_cards")
async def show_tech_cards(callback: CallbackQuery):
    """Показывает технологические карты"""
    tech_cards_data = CONTENT.get("tech_cards", {})

    text = f"<b>{tech_cards_data.get('title', '📋 Технологические карты')}</b>\n\n"
    text += f"{tech_cards_data.get('description', '')}\n\n"

    # Показываем первый рецепт
    recipes = tech_cards_data.get("recipes", [])
    if recipes:
        recipe = recipes[0]
        text += f"<b>{recipe['dish']}</b>\n\n"

        text += "<b>Ингредиенты:</b>\n"
        for ingredient in recipe["ingredients"]:
            text += f"{ingredient}\n"

        text += "\n<b>Приготовление:</b>\n"
        for step in recipe["steps"]:
            text += f"{step}\n"

        text += f"\n⏱️ Время: {recipe['time']}\n"
        text += f"🌡️ Температура: {recipe['temperature']}\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_kitchen()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_tech_cards: {e}")
        await callback.answer("Ошибка загрузки карт")


@router.callback_query(F.data == "kitchen_discount")
async def show_kitchen_discount(callback: CallbackQuery):
    """Показывает информацию о скидках для сотрудников"""
    discount_data = CONTENT.get("employee_discount", {})

    text = f"<b>{discount_data.get('title', '💼 Скидка для сотрудников')}</b>\n\n"
    text += f"{discount_data.get('description', '')}\n\n"

    for benefit in discount_data.get("benefits", []):
        text += f"{benefit}\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_kitchen()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_kitchen_discount: {e}")
        await callback.answer("Ошибка загрузки информации")


@router.callback_query(F.data == "kitchen_hygiene")
async def show_hygiene_rules(callback: CallbackQuery):
    """Показывает правила гигиены"""
    hygiene_data = CONTENT.get("hygiene", {})

    text = f"<b>{hygiene_data.get('title', '🧼 Правила гигиены')}</b>\n\n"

    for rule in hygiene_data.get("rules", []):
        text += f"{rule}\n"

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_kitchen()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_hygiene_rules: {e}")
        await callback.answer("Ошибка загрузки правил")

"""
Handler для раздела "Отдел продаж".

Обрабатывает все callback'ы связанные с:
- Общей информацией об отделе
- Открытием и закрытием парка
- Работой с кассой
- Работой с amoCRM
- Работой с гостями
- Базой знаний о мошенниках

Это самый объемный handler в проекте.
"""

import json
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

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
    get_back_to_sales_general,
    get_back_to_opening,
    get_back_to_cash,
    get_back_to_crm,
    get_back_to_guests,
    get_back_to_scripts,
    get_back_to_fraud
)
from states.menu_states import MenuStates
from utils.logger import logger

# Создаем router для этого модуля
router = Router(name='sales')

# Загружаем контент из JSON
CONTENT_PATH = Path(__file__).parent.parent / "content" / "texts" / "sales.json"

try:
    with open(CONTENT_PATH, 'r', encoding='utf-8') as f:
        CONTENT = json.load(f)
    logger.info("✅ Контент sales.json загружен успешно")
except FileNotFoundError:
    logger.error(f"❌ Файл {CONTENT_PATH} не найден!")
    CONTENT = {}
except json.JSONDecodeError as e:
    logger.error(f"❌ Ошибка парсинга JSON: {e}")
    CONTENT = {}


# ========== ГЛАВНОЕ МЕНЮ РАЗДЕЛА ==========

@router.callback_query(F.data == "sales")
async def show_sales_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает главное меню раздела "Отдел продаж"."""
    await state.set_state(MenuStates.sales_menu)
    
    main_menu_text = CONTENT.get("main_menu", {})
    text = (
        f"<b>{main_menu_text.get('title', '🔴 Отдел продаж')}</b>\n\n"
        f"{main_menu_text.get('description', 'Выберите интересующий раздел:')}"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_sales_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_sales_menu: {e}")
        await callback.answer("Произошла ошибка")


# ========== ОБЩАЯ ИНФОРМАЦИЯ ==========

@router.callback_query(F.data == "sales_general")
async def show_sales_general_menu(callback: CallbackQuery):
    """Показывает меню общей информации об отделе."""
    general_info = CONTENT.get("general_info", {})
    
    text = (
        f"<b>{general_info.get('title', '📋 Общая информация')}</b>\n\n"
        "Выберите интересующий подраздел:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_sales_general_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_sales_general_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data == "sales_gen_structure")
async def show_org_structure(callback: CallbackQuery):
    """Показывает организационную структуру отдела."""
    general_info = CONTENT.get("general_info", {})
    structure = general_info.get("org_structure", {})
    
    text = f"<b>{structure.get('title', '👥 Организационная структура')}</b>\n\n"
    
    positions = structure.get("positions", [])
    for position in positions:
        text += f"<b>{position.get('role')}</b>\n"
        if 'name' in position:
            text += f"👤 {position.get('name')}\n"
        if 'count' in position:
            text += f"👥 {position.get('count')}\n"
        if 'phone' in position:
            text += f"📱 <a href='tel:{position.get('phone')}'>{position.get('phone')}</a>\n"
        text += f"\n📋 <b>Обязанности:</b>\n{position.get('responsibilities', '')}\n\n"
        text += "─────────\n\n"
    
    text += f"<b>Иерархия:</b>\n{structure.get('hierarchy', '')}"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_sales_general(),
            disable_web_page_preview=True
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_org_structure: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_gen_appearance")
async def show_appearance(callback: CallbackQuery):
    """Показывает требования к внешнему виду."""
    general_info = CONTENT.get("general_info", {})
    appearance = general_info.get("appearance", {})
    dress_code = appearance.get("dress_code", {})
    
    text = f"<b>{appearance.get('title', '👔 Внешний вид сотрудников')}</b>\n\n"
    
    text += f"<b>{dress_code.get('title', 'Дресс-код:')}</b>\n\n"
    text += "\n".join(dress_code.get("requirements", []))
    text += "\n\n<b>❌ Недопустимо:</b>\n"
    text += "\n".join(dress_code.get("forbidden", []))
    text += f"\n\n{appearance.get('hygiene', '')}"
    text += f"\n\n{appearance.get('badge', '')}"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_sales_general()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_appearance: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_gen_rules")
async def show_work_rules(callback: CallbackQuery):
    """Показывает правила прихода и ухода."""
    general_info = CONTENT.get("general_info", {})
    rules = general_info.get("work_rules", {})
    
    text = f"<b>{rules.get('title', '⏰ Правила прихода и ухода')}</b>\n\n"
    
    text += "<b>📥 Приход на работу:</b>\n"
    text += "\n".join(rules.get("arrival", []))
    
    text += "\n\n<b>⚙️ Во время смены:</b>\n"
    text += "\n".join(rules.get("during_shift", []))
    
    text += "\n\n<b>📤 Уход с работы:</b>\n"
    text += "\n".join(rules.get("departure", []))
    
    text += f"\n\n{rules.get('punctuality', '')}"
    
    try:
        # Если текст слишком длинный, разбиваем
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_sales_general()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_sales_general()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_work_rules: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_gen_atmosphere")
async def show_atmosphere(callback: CallbackQuery):
    """Показывает информацию об атмосфере в коллективе."""
    general_info = CONTENT.get("general_info", {})
    atmosphere = general_info.get("atmosphere", {})
    
    text = f"<b>{atmosphere.get('title', '🌟 Атмосфера в коллективе')}</b>\n\n"
    
    text += "<b>Наши ценности:</b>\n"
    text += "\n".join(atmosphere.get("values", []))
    
    text += "\n\n<b>Правила общения:</b>\n"
    text += "\n".join(atmosphere.get("rules", []))
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_sales_general()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_atmosphere: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_gen_schedule")
async def show_schedule(callback: CallbackQuery):
    """Показывает информацию о графике работы."""
    general_info = CONTENT.get("general_info", {})
    schedule = general_info.get("schedule", {})
    
    text = f"<b>{schedule.get('title', '📅 График работы')}</b>\n\n"
    text += f"{schedule.get('description', '')}\n\n"
    text += "\n".join(schedule.get("rules", []))
    text += f"\n\n<b>🔗 Ссылка на график:</b>\n{schedule.get('link', '')}"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_sales_general(),
            disable_web_page_preview=True
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_schedule: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_gen_chats")
async def show_chats(callback: CallbackQuery):
    """Показывает информацию о чатах отдела."""
    general_info = CONTENT.get("general_info", {})
    chats = general_info.get("chats", {})
    
    text = f"<b>{chats.get('title', '💬 Чаты отдела')}</b>\n\n"
    
    for chat in chats.get("list", []):
        text += f"<b>{chat.get('name')}</b>\n"
        text += f"🔗 {chat.get('link')}\n"
        text += f"📋 <b>Назначение:</b> {chat.get('purpose')}\n\n"
        
        if 'rules' in chat:
            text += "<b>Правила:</b>\n"
            text += "\n".join(chat.get('rules'))
            text += "\n\n"
        
        text += "─────────\n\n"
    
    text += f"{chats.get('important', '')}"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_sales_general(),
            disable_web_page_preview=True
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_chats: {e}")
        await callback.answer("Ошибка загрузки")


# ========== ОТКРЫТИЕ И ЗАКРЫТИЕ ПАРКА ==========

@router.callback_query(F.data == "sales_opening")
async def show_opening_menu(callback: CallbackQuery):
    """Показывает меню открытия/закрытия парка."""
    opening_closing = CONTENT.get("opening_closing", {})
    
    text = (
        f"<b>{opening_closing.get('title', '🏢 Открытие и закрытие парка')}</b>\n\n"
        "Выберите интересующий раздел:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_opening_closing_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_opening_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data == "sales_open_park")
async def show_park_opening(callback: CallbackQuery):
    """Показывает инструкцию по открытию парка."""
    opening_closing = CONTENT.get("opening_closing", {})
    opening = opening_closing.get("opening", {})
    
    text = f"<b>{opening.get('title', '☀️ Открытие парка')}</b>\n\n"
    text += f"{opening.get('time', '')}\n\n"
    text += "<b>📋 Чек-лист открытия:</b>\n\n"
    text += "\n".join(opening.get("checklist", []))
    
    text += "\n\n<b>⚠️ Частые проблемы:</b>\n"
    text += "\n".join(opening.get("common_issues", []))
    
    # Отправляем видео, если есть
    video_file = opening.get("video_instruction")
    if video_file:
        video_path = Path(__file__).parent.parent / "content" / "media" / "videos" / video_file
        
        try:
            if video_path.exists():
                await callback.message.answer_video(
                    video=FSInputFile(video_path),
                    caption="🎬 Видео-инструкция по открытию парка"
                )
        except Exception as e:
            logger.warning(f"Не удалось отправить видео: {e}")
    
    try:
        # Разбиваем длинный текст
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_opening()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_opening()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_park_opening: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_close_park")
async def show_park_closing(callback: CallbackQuery):
    """Показывает инструкцию по закрытию парка."""
    opening_closing = CONTENT.get("opening_closing", {})
    closing = opening_closing.get("closing", {})
    
    text = f"<b>{closing.get('title', '🌙 Закрытие парка')}</b>\n\n"
    text += f"{closing.get('time', '')}\n\n"
    text += "<b>📋 Чек-лист закрытия:</b>\n\n"
    text += "\n".join(closing.get("checklist", []))
    
    text += "\n\n<b>⚠️ Важные примечания:</b>\n"
    text += "\n".join(closing.get("important_notes", []))
    
    # Отправляем видео, если есть
    video_file = closing.get("video_instruction")
    if video_file:
        video_path = Path(__file__).parent.parent / "content" / "media" / "videos" / video_file
        
        try:
            if video_path.exists():
                await callback.message.answer_video(
                    video=FSInputFile(video_path),
                    caption="🎬 Видео-инструкция по закрытию парка"
                )
        except Exception as e:
            logger.warning(f"Не удалось отправить видео: {e}")
    
    try:
        # Разбиваем длинный текст
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_opening()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_opening()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_park_closing: {e}")
        await callback.answer("Ошибка загрузки")


# ========== РАБОТА С КАССОЙ ==========

@router.callback_query(F.data == "sales_cash")
async def show_cash_menu(callback: CallbackQuery):
    """Показывает меню работы с кассой."""
    text = "<b>💳 Работа с кассой</b>\n\nВыберите интересующий раздел:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_cash_register_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_cash_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data == "sales_cash_video")
async def send_cash_video(callback: CallbackQuery):
    """Отправляет видео-инструкцию по работе с кассой."""
    cash_data = CONTENT.get("cash_register", {})
    video_file = cash_data.get("video_instruction")
    
    if video_file:
        video_path = Path(__file__).parent.parent / "content" / "media" / "videos" / video_file
        
        try:
            if video_path.exists():
                await callback.message.answer_video(
                    video=FSInputFile(video_path),
                    caption="🎬 Полная видео-инструкция по работе с кассой\n\n"
                            "Посмотрите внимательно все этапы работы.",
                    reply_markup=get_back_to_cash()
                )
                await callback.answer("Видео отправлено ✅")
            else:
                await callback.answer(
                    "Видео временно недоступно. Обратитесь к администратору.",
                    show_alert=True
                )
        except Exception as e:
            logger.error(f"Ошибка отправки видео: {e}")
            await callback.answer("Ошибка отправки видео")
    else:
        await callback.answer("Видео не найдено", show_alert=True)


@router.callback_query(F.data.startswith("sales_cash_"))
async def show_cash_instructions(callback: CallbackQuery):
    """Показывает инструкции по работе с кассой."""
    section = callback.data.replace("sales_cash_", "")
    
    cash_data = CONTENT.get("cash_register", {})
    section_data = cash_data.get(section, {})
    
    if not section_data:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    
    text = f"<b>{section_data.get('title', '')}</b>\n\n"
    
    # Формируем текст в зависимости от раздела
    if 'steps' in section_data:
        text += "\n".join(section_data['steps'])
    
    if 'tips' in section_data:
        text += "\n\n<b>💡 Полезные советы:</b>\n"
        text += "\n".join(section_data['tips'])
    
    if 'when' in section_data:
        text += f"\n\n<b>⚠️ Когда применять:</b>\n{section_data['when']}"
    
    if 'important' in section_data:
        text += "\n\n<b>❗ Важно:</b>\n"
        text += "\n".join(section_data['important'])
    
    if 'errors' in section_data:
        text += "\n\n<b>Типичные проблемы:</b>\n\n"
        for error in section_data['errors']:
            text += f"<b>❌ {error.get('problem')}</b>\n"
            text += f"✅ Решение:\n{error.get('solution')}\n\n"
    
    if 'phone' in section_data:
        text += f"\n\n<b>📞 Телефон поддержки:</b> {section_data['phone']}"
        text += f"\n<b>⏰ Режим работы:</b> {section_data.get('hours', '')}"
        if 'what_to_say' in section_data:
            text += f"\n\n{section_data['what_to_say']}"
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_cash()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_cash(),
                disable_web_page_preview=True
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_cash_instructions: {e}")
        await callback.answer("Ошибка загрузки")


# ========== РАБОТА С CRM ==========

@router.callback_query(F.data == "sales_crm")
async def show_crm_menu(callback: CallbackQuery):
    """Показывает меню работы с amoCRM."""
    text = "<b>📊 Работа с amoCRM</b>\n\nВыберите интересующий раздел:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_crm_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_crm_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data == "sales_crm_video")
async def send_crm_video(callback: CallbackQuery):
    """Отправляет видео-инструкцию по работе с CRM."""
    crm_data = CONTENT.get("crm", {})
    video_file = crm_data.get("video_instruction")
    
    if video_file:
        video_path = Path(__file__).parent.parent / "content" / "media" / "videos" / video_file
        
        try:
            if video_path.exists():
                await callback.message.answer_video(
                    video=FSInputFile(video_path),
                    caption="🎬 Видео-инструкция по работе с amoCRM",
                    reply_markup=get_back_to_crm()
                )
                await callback.answer("Видео отправлено ✅")
            else:
                await callback.answer("Видео временно недоступно", show_alert=True)
        except Exception as e:
            logger.error(f"Ошибка отправки видео CRM: {e}")
            await callback.answer("Ошибка отправки видео")
    else:
        await callback.answer("Видео не найдено", show_alert=True)


@router.callback_query(F.data.startswith("sales_crm_"))
async def show_crm_instructions(callback: CallbackQuery):
    """Показывает инструкции по работе с CRM."""
    section = callback.data.replace("sales_crm_", "")
    
    crm_data = CONTENT.get("crm", {})
    section_mapping = {
        "login": "login",
        "create": "create_lead",
        "funnel": "funnel_stages",
        "tasks": "tasks",
        "client": "client_card",
        "rules": "rules"
    }
    
    section_key = section_mapping.get(section)
    if not section_key:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    
    section_data = crm_data.get(section_key, {})
    
    text = f"<b>{section_data.get('title', '')}</b>\n\n"
    
    if 'url' in section_data:
        text += f"🔗 <b>Ссылка:</b> {section_data['url']}\n"
    if 'credentials' in section_data:
        text += f"{section_data['credentials']}\n\n"
    if 'description' in section_data:
        text += f"{section_data['description']}\n\n"
    if 'when' in section_data:
        text += f"<b>Когда создавать:</b>\n{section_data['when']}\n\n"
    
    if 'steps' in section_data:
        text += "<b>Шаги:</b>\n"
        text += "\n\n".join(section_data['steps'])
    
    if 'stages' in section_data:
        text += "<b>Этапы воронки:</b>\n\n"
        for stage in section_data['stages']:
            text += f"<b>{stage.get('name')}</b>\n"
            text += f"{stage.get('description')}\n"
            text += f"✅ Действие: {stage.get('action')}\n\n"
    
    if 'create_task' in section_data:
        text += "\n".join(section_data['create_task'])
        text += "\n\n"
    
    if 'types' in section_data:
        text += "<b>Типы задач:</b>\n"
        text += "\n".join(section_data['types'])
        text += "\n\n"
    
    if 'deadline' in section_data:
        text += f"{section_data['deadline']}\n\n"
    
    if 'required_fields' in section_data:
        text += "<b>Обязательные поля:</b>\n"
        text += "\n".join(section_data['required_fields'])
        text += "\n\n"
    
    if 'tags' in section_data:
        text += "\n".join(section_data['tags'])
        text += "\n\n"
    
    if 'must_do' in section_data:
        text += "<b>✅ Обязательно:</b>\n"
        text += "\n".join(section_data['must_do'])
        text += "\n\n"
    
    if 'forbidden' in section_data:
        text += "<b>❌ Запрещено:</b>\n"
        text += "\n".join(section_data['forbidden'])
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_crm()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_crm(),
                disable_web_page_preview=True
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_crm_instructions: {e}")
        await callback.answer("Ошибка загрузки")


# ========== РАБОТА С ГОСТЯМИ ==========

@router.callback_query(F.data == "sales_guests")
async def show_guests_menu(callback: CallbackQuery):
    """Показывает меню работы с гостями."""
    text = "<b>🤝 Работа с гостями</b>\n\nВыберите интересующий раздел:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_guests_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_guests_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data == "sales_guests_scripts")
async def show_scripts_menu(callback: CallbackQuery):
    """Показывает меню скриптов продаж."""
    text = "<b>💬 Скрипты продаж</b>\n\nВыберите этап продажи:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_sales_scripts_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_scripts_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("sales_script_"))
async def show_script(callback: CallbackQuery):
    """Показывает конкретный скрипт продаж."""
    script_type = callback.data.replace("sales_script_", "")
    
    guest_data = CONTENT.get("guest_interaction", {})
    scripts = guest_data.get("sales_scripts", {})
    script = scripts.get(script_type, {})
    
    if not script:
        await callback.answer("Скрипт не найден", show_alert=True)
        return
    
    text = f"<b>{script.get('title', '')}</b>\n\n"
    
    # Формирование текста в зависимости от типа скрипта
    if 'good' in script:
        text += "<b>✅ Правильные фразы:</b>\n"
        text += "\n".join(script['good'])
        text += "\n\n"
    
    if 'bad' in script:
        text += "<b>❌ Неправильные фразы:</b>\n"
        text += "\n".join(script['bad'])
        text += "\n\n"
    
    if 'rules' in script:
        text += "<b>📋 Правила:</b>\n"
        text += "\n".join(script['rules'])
        text += "\n\n"
    
    if 'questions' in script:
        text += "<b>Вопросы для выявления:</b>\n"
        text += "\n".join(script['questions'])
        text += "\n\n"
    
    if 'listen' in script:
        text += f"{script['listen']}\n\n"
    
    if 'structure' in script:
        text += f"<b>Структура:</b> {script['structure']}\n\n"
    
    if 'examples' in script:
        text += "<b>Примеры:</b>\n\n"
        for example in script['examples']:
            text += f"<b>Услуга:</b> {example.get('service')}\n"
            text += f"❌ Плохо: {example.get('bad')}\n"
            text += f"✅ Хорошо: {example.get('good')}\n\n"
    
    if 'emphasis' in script:
        text += "<b>На что делать упор:</b>\n"
        text += "\n".join(script['emphasis'])
        text += "\n\n"
    
    if 'common' in script:
        text += "<b>Типичные возражения:</b>\n\n"
        for obj in script['common']:
            text += f"<b>Возражение:</b> {obj.get('objection')}\n"
            text += f"❌ Неправильно: {obj.get('wrong')}\n"
            text += f"✅ Правильно: {obj.get('right')}\n\n"
    
    if 'technique' in script:
        text += "<b>Техника работы:</b>\n"
        text += "\n".join(script['technique'])
        text += "\n\n"
    
    if 'signals' in script:
        text += "\n".join(script['signals'])
        text += "\n\n"
    
    if 'techniques' in script:
        text += "<b>Техники закрытия:</b>\n\n"
        for tech in script['techniques']:
            text += f"<b>{tech.get('name')}</b>\n"
            text += f"Пример: {tech.get('example')}\n\n"
    
    if 'final_words' in script:
        text += "<b>Завершающие фразы:</b>\n"
        text += "\n".join(script['final_words'])
        text += "\n\n"
    
    if 'what' in script:
        text += f"{script['what']}\n\n"
    
    if 'when' in script:
        text += f"<b>Когда предлагать:</b> {script['when']}\n\n"
    
    if 'examples' in script and script_type in ['upsell', 'crosssell']:
        text += "<b>Примеры:</b>\n"
        text += "\n".join(script['examples'])
        text += "\n\n"
    
    if 'rules' in script and script_type in ['upsell']:
        text += "<b>Правила:</b>\n"
        text += "\n".join(script['rules'])
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_scripts()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_scripts()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_script: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_guests_children")
async def show_children_adults(callback: CallbackQuery):
    """Показывает информацию о работе с детьми и взрослыми."""
    guest_data = CONTENT.get("guest_interaction", {})
    children_adults = guest_data.get("children_adults", {})
    
    text = f"<b>{children_adults.get('title', '')}</b>\n\n"
    text += "<b>👶 Работа с детьми:</b>\n"
    text += "\n".join(children_adults.get('children', []))
    text += "\n\n<b>👨‍💼 Работа со взрослыми:</b>\n"
    text += "\n".join(children_adults.get('adults', []))
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_guests()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_children_adults: {e}")
        await callback.answer("Ошибка загрузки")


@router.callback_query(F.data == "sales_guests_contacts")
async def show_contact_collection(callback: CallbackQuery):
    """Показывает информацию о сборе контактов."""
    guest_data = CONTENT.get("guest_interaction", {})
    contacts = guest_data.get("contact_collection", {})
    
    text = f"<b>{contacts.get('title', '')}</b>\n\n"
    text += f"<b>Зачем собирать контакты:</b>\n{contacts.get('why', '')}\n\n"
    text += "<b>Способы сбора:</b>\n"
    text += "\n".join(contacts.get('how', []))
    text += f"\n\n<b>💬 {contacts.get('script', '')}</b>"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_guests()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_contact_collection: {e}")
        await callback.answer("Ошибка загрузки")


# ========== БАЗА ЗНАНИЙ О МОШЕННИКАХ ==========

@router.callback_query(F.data == "sales_fraud")
async def show_fraud_menu(callback: CallbackQuery):
    """Показывает меню базы знаний о мошенниках."""
    fraud_data = CONTENT.get("fraud_prevention", {})
    
    text = (
        f"<b>{fraud_data.get('title', '')}</b>\n\n"
        f"{fraud_data.get('description', '')}\n\n"
        "Выберите тип ситуации:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_fraud_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_fraud_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("sales_fraud_"))
async def show_fraud_info(callback: CallbackQuery):
    """Показывает информацию о конкретной мошеннической схеме."""
    fraud_type = callback.data.replace("sales_fraud_", "")
    
    fraud_data = CONTENT.get("fraud_prevention", {})
    
    type_mapping = {
        "money": "fake_money",
        "refund": "refund_scam",
        "aggressive": "aggressive_clients",
        "theft": "theft",
        "freepass": "free_pass"
    }
    
    fraud_key = type_mapping.get(fraud_type)
    if not fraud_key:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    
    fraud_info = fraud_data.get(fraud_key, {})
    
    text = f"<b>{fraud_info.get('title', '')}</b>\n\n"
    
    if 'how_to_spot' in fraud_info:
        text += "\n".join(fraud_info['how_to_spot'])
        text += "\n\n"
    
    if 'what_to_do' in fraud_info:
        text += "<b>Что делать:</b>\n"
        text += "\n".join(fraud_info['what_to_do'])
        text += "\n\n"
    
    if 'warning' in fraud_info:
        text += f"{fraud_info['warning']}\n\n"
    
    if 'schemes' in fraud_info:
        text += "<b>Типичные схемы:</b>\n\n"
        for scheme in fraud_info['schemes']:
            text += f"<b>{scheme.get('name')}</b>\n"
            text += f"{scheme.get('description')}\n\n"
            text += "<b>Как предотвратить:</b>\n"
            text += "\n".join(scheme.get('how_to_prevent', []))
            text += "\n\n─────────\n\n"
    
    if 'types' in fraud_info:
        text += "<b>Типы агрессивных клиентов:</b>\n"
        text += "\n".join(fraud_info['types'])
        text += "\n\n"
    
    if 'what_to_do' in fraud_info and fraud_type == "aggressive":
        text += "\n".join(fraud_info['what_to_do'])
        text += "\n\n"
    
    if 'phrases' in fraud_info:
        phrases = fraud_info['phrases']
        text += "\n".join(phrases.get('good', []))
        text += "\n\n"
        text += "\n".join(phrases.get('bad', []))
        text += "\n\n"
    
    if 'signs' in fraud_info:
        text += "\n".join(fraud_info['signs'])
        text += "\n\n"
    
    if 'prevention' in fraud_info:
        text += "\n".join(fraud_info['prevention'])
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_fraud()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_fraud()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_fraud_info: {e}")
        await callback.answer("Ошибка загрузки")

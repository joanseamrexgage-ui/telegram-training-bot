"""
Handler для раздела "Спортивный отдел".

Обрабатывает все callback'ы связанные с:
- Общей информацией об отделе
- Инструкциями по оборудованию
- Правилами безопасности
- Действиями при травмах
- Экстренными контактами
"""

import json
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from keyboards.sport_kb import (
    get_sport_menu,
    get_sport_general_menu,
    get_equipment_menu,
    get_safety_menu,
    get_injury_menu,
    get_back_to_sport,
    get_back_to_sport_general,
    get_back_to_equipment,
    get_back_to_safety,
    get_back_to_injury
)
from states.menu_states import MenuStates
from utils.logger import logger

# Создаем router для этого модуля
router = Router(name='sport')

# Загружаем контент из JSON
CONTENT_PATH = Path(__file__).parent.parent / "content" / "texts" / "sport.json"

try:
    with open(CONTENT_PATH, 'r', encoding='utf-8') as f:
        CONTENT = json.load(f)
    logger.info("✅ Контент sport.json загружен успешно")
except FileNotFoundError:
    logger.error(f"❌ Файл {CONTENT_PATH} не найден!")
    CONTENT = {}
except json.JSONDecodeError as e:
    logger.error(f"❌ Ошибка парсинга JSON: {e}")
    CONTENT = {}


# ========== ГЛАВНОЕ МЕНЮ РАЗДЕЛА ==========

@router.callback_query(F.data == "sport")
async def show_sport_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает главное меню раздела "Спортивный отдел"."""
    # ИСПРАВЛЕНИЕ: Добавлено подробное логирование для диагностики ошибок
    logger.info(f"Пользователь {callback.from_user.id} открывает меню 'Спортивный отдел'")

    # ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: было MenuStates.sport_menu (не существует)
    # Правильное состояние: MenuStates.sport_department (определено в states/menu_states.py:85)
    await state.set_state(MenuStates.sport_department)

    main_menu_text = CONTENT.get("main_menu", {})
    text = (
        f"<b>{main_menu_text.get('title', '🟡 Спортивный отдел')}</b>\n\n"
        f"{main_menu_text.get('description', 'Выберите интересующий раздел:')}"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_sport_menu()
        )
        await callback.answer()
        logger.info(f"Меню 'Спортивный отдел' успешно показано пользователю {callback.from_user.id}")
    except Exception as e:
        # ИСПРАВЛЕНИЕ: Расширенное логирование ошибок с полным traceback
        logger.error(f"❌ Ошибка в show_sport_menu для пользователя {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("Произошла ошибка")


# ========== ОБЩАЯ ИНФОРМАЦИЯ ==========

@router.callback_query(F.data == "sport_general")
async def show_sport_general_menu(callback: CallbackQuery):
    """Показывает меню общей информации об отделе."""
    general_info = CONTENT.get("general_info", {})
    
    text = (
        f"<b>{general_info.get('title', '📋 Общая информация')}</b>\n\n"
        "Выберите интересующий подраздел:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_sport_general_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_sport_general_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("sport_gen_"))
async def show_general_info(callback: CallbackQuery):
    """Показывает подразделы общей информации."""
    section = callback.data.replace("sport_gen_", "")
    
    general_info = CONTENT.get("general_info", {})
    
    section_mapping = {
        "structure": "org_structure",
        "appearance": "appearance",
        "rules": "work_rules",
        "physical": "physical_requirements",
        "schedule": "schedule",
        "chats": "chats"
    }
    
    section_key = section_mapping.get(section)
    if not section_key:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    
    section_data = general_info.get(section_key, {})
    text = f"<b>{section_data.get('title', '')}</b>\n\n"
    
    # Формирование текста в зависимости от раздела
    if section == "structure":
        for position in section_data.get("positions", []):
            text += f"<b>{position.get('role')}</b>\n"
            if 'name' in position:
                text += f"👤 {position.get('name')}\n"
            if 'count' in position:
                text += f"👥 {position.get('count')}\n"
            if 'phone' in position:
                text += f"📱 <a href='tel:{position.get('phone')}'>{position.get('phone')}</a>\n"
            text += f"\n📋 <b>Обязанности:</b>\n{position.get('responsibilities', '')}\n\n"
            text += "─────────\n\n"
        text += f"<b>Иерархия:</b>\n{section_data.get('hierarchy', '')}"
    
    elif section == "appearance":
        dress_code = section_data.get("dress_code", {})
        text += f"<b>{dress_code.get('title', '')}</b>\n\n"
        text += "\n".join(dress_code.get("requirements", []))
        text += "\n\n<b>❌ Недопустимо:</b>\n"
        text += "\n".join(dress_code.get("forbidden", []))
        text += f"\n\n{section_data.get('safety_gear', '')}"
        text += f"\n\n{section_data.get('hygiene', '')}"
    
    elif section == "rules":
        text += "<b>📥 Приход на работу:</b>\n"
        text += "\n".join(section_data.get("arrival", []))
        text += "\n\n<b>⚙️ Во время смены:</b>\n"
        text += "\n".join(section_data.get("during_shift", []))
        text += "\n\n<b>📤 Уход с работы:</b>\n"
        text += "\n".join(section_data.get("departure", []))
    
    elif section == "physical":
        text += "<b>Требования:</b>\n"
        text += "\n".join(section_data.get("requirements", []))
        text += f"\n\n{section_data.get('medical', '')}"
    
    elif section == "schedule":
        text += f"{section_data.get('description', '')}\n\n"
        text += "\n".join(section_data.get("shifts", []))
        text += f"\n\n<b>🔗 Ссылка на график:</b>\n{section_data.get('link', '')}"
    
    elif section == "chats":
        for chat in section_data.get("list", []):
            text += f"<b>{chat.get('name')}</b>\n"
            text += f"🔗 {chat.get('link')}\n"
            text += f"📋 <b>Назначение:</b> {chat.get('purpose')}\n\n"
            if 'rules' in chat:
                text += "<b>Правила:</b>\n"
                text += "\n".join(chat.get('rules'))
                text += "\n\n"
            text += "─────────\n\n"
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_sport_general()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_sport_general(),
                disable_web_page_preview=True
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_general_info: {e}")
        await callback.answer("Ошибка загрузки")


# ========== ИНСТРУКЦИИ ПО ОБОРУДОВАНИЮ ==========

@router.callback_query(F.data == "sport_equipment")
async def show_equipment_menu(callback: CallbackQuery):
    """Показывает меню инструкций по оборудованию."""
    text = "<b>⚙️ Инструкции по оборудованию</b>\n\nВыберите аттракцион:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_equipment_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_equipment_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("sport_equip_"))
async def show_equipment_instructions(callback: CallbackQuery):
    """Показывает инструкции по конкретному оборудованию."""
    equipment_type = callback.data.replace("sport_equip_", "")
    
    equipment_data = CONTENT.get("equipment", {})
    
    type_mapping = {
        "trampoline": "trampoline",
        "climbing": "climbing_wall",
        "rope": "rope_park",
        "games": "game_machines",
        "labyrinth": "labyrinth"
    }
    
    equip_key = type_mapping.get(equipment_type)
    if not equip_key:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    
    equip_info = equipment_data.get(equip_key, {})
    
    text = f"<b>{equip_info.get('title', '')}</b>\n\n"
    
    # Отправляем видео если есть
    video_file = equip_info.get("video_instruction")
    if video_file:
        video_path = Path(__file__).parent.parent / "content" / "media" / "videos" / video_file
        try:
            if video_path.exists():
                await callback.message.answer_video(
                    video=FSInputFile(video_path),
                    caption=f"🎬 Видео-инструкция: {equip_info.get('title')}"
                )
        except Exception as e:
            logger.warning(f"Не удалось отправить видео: {e}")
    
    # Формируем текст инструкции
    if 'startup' in equip_info:
        text += "\n".join(equip_info['startup'])
        text += "\n\n"
    
    if 'belay_system' in equip_info:
        text += "\n".join(equip_info['belay_system'])
        text += "\n\n"
    
    if 'equipment' in equip_info:
        text += "\n".join(equip_info['equipment'])
        text += "\n\n"
    
    if 'instructor_training' in equip_info:
        text += "\n".join(equip_info['instructor_training'])
        text += "\n\n"
    
    if 'rules' in equip_info:
        text += "\n".join(equip_info['rules'])
        text += "\n\n"
    
    if 'instructor_actions' in equip_info:
        text += "\n".join(equip_info['instructor_actions'])
        text += "\n\n"
    
    if 'rescue' in equip_info:
        text += "<b>🚁 Спасение застрявшего:</b>\n"
        text += "\n".join(equip_info['rescue'])
        text += "\n\n"
    
    if 'emergency' in equip_info:
        text += f"{equip_info['emergency']}\n\n"
    
    if 'common_issues' in equip_info:
        text += "\n".join(equip_info['common_issues'])
        text += "\n\n"
    
    if 'max_weight' in equip_info:
        text += f"{equip_info['max_weight']}\n\n"
    
    if 'lost_child' in equip_info:
        text += "\n".join(equip_info['lost_child'])
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_equipment()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_equipment()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_equipment_instructions: {e}")
        await callback.answer("Ошибка загрузки")


# ========== ПРАВИЛА БЕЗОПАСНОСТИ ==========

@router.callback_query(F.data == "sport_safety")
async def show_safety_menu(callback: CallbackQuery):
    """Показывает меню правил безопасности."""
    text = "<b>🛡️ Правила безопасности</b>\n\nВыберите раздел:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_safety_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_safety_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("sport_safety_"))
async def show_safety_rules(callback: CallbackQuery):
    """Показывает правила безопасности."""
    safety_type = callback.data.replace("sport_safety_", "")
    
    safety_data = CONTENT.get("safety_rules", {})
    
    text = f"<b>{safety_data.get('title', '🛡️ Правила безопасности')}</b>\n\n"
    
    if safety_type == "general":
        text += "\n".join(safety_data.get("general", []))
    elif safety_type == "prohibited":
        text += "\n".join(safety_data.get("prohibited", []))
    elif safety_type == "age":
        text += "\n".join(safety_data.get("age_restrictions", []))
    elif safety_type == "weight":
        text += "\n".join(safety_data.get("weight_limits", []))
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_safety()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_safety()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_safety_rules: {e}")
        await callback.answer("Ошибка загрузки")


# ========== ДЕЙСТВИЯ ПРИ ТРАВМАХ ==========

@router.callback_query(F.data == "sport_injury")
async def show_injury_menu(callback: CallbackQuery):
    """Показывает меню действий при травмах."""
    text = "<b>🏥 Действия при травмах</b>\n\nВыберите раздел:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_injury_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_injury_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("sport_injury_"))
async def show_injury_instructions(callback: CallbackQuery):
    """Показывает инструкции по оказанию помощи."""
    injury_type = callback.data.replace("sport_injury_", "")
    
    injury_data = CONTENT.get("injury_response", {})
    
    type_mapping = {
        "kit": "first_aid_kit",
        "minor": "minor_injuries",
        "serious": "serious_injuries",
        "cpr": "cpr",
        "psych": "psychological_help"
    }
    
    injury_key = type_mapping.get(injury_type)
    if not injury_key:
        await callback.answer("Раздел не найден", show_alert=True)
        return
    
    text = f"<b>{injury_data.get('title', '🏥 Действия при травмах')}</b>\n\n"
    text += "\n".join(injury_data.get(injury_key, []))
    
    try:
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_injury()
                    )
                else:
                    await callback.message.answer(text=part)
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_injury()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_injury_instructions: {e}")
        await callback.answer("Ошибка загрузки")


# ========== ЭКСТРЕННЫЕ КОНТАКТЫ ==========

@router.callback_query(F.data == "sport_contacts")
async def show_emergency_contacts(callback: CallbackQuery):
    """Показывает экстренные контакты."""
    contacts_data = CONTENT.get("emergency_contacts", {})
    
    text = f"<b>{contacts_data.get('title', '📞 Экстренные контакты')}</b>\n\n"
    text += "\n".join(contacts_data.get("services", []))
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_sport(),
            disable_web_page_preview=True
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_emergency_contacts: {e}")
        await callback.answer("Ошибка загрузки")

"""
Handler для раздела "Общая информация".

Обрабатывает все callback'ы связанные с:
- Адресами парков
- Важными телефонами
- Внештатными ситуациями
- Зарплатой и авансом
- Приказами
- Скидками партнеров
"""

import json
from pathlib import Path

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from keyboards.general_info_kb import (
    get_general_info_menu,
    get_parks_menu,
    get_emergency_menu,
    get_orders_menu,
    get_discounts_parks_menu,
    get_back_to_general_info,
    get_back_to_addresses,
    get_back_to_phones,
    get_back_to_emergency,
    get_back_to_discounts
)
from states.menu_states import MenuStates
from utils.logger import logger

# Создаем router для этого модуля
router = Router(name='general_info')

# Загружаем контент из JSON
CONTENT_PATH = Path(__file__).parent.parent / "content" / "texts" / "general_info.json"

try:
    with open(CONTENT_PATH, 'r', encoding='utf-8') as f:
        CONTENT = json.load(f)
    logger.info("✅ Контент general_info.json загружен успешно")
except FileNotFoundError:
    logger.error(f"❌ Файл {CONTENT_PATH} не найден!")
    CONTENT = {}
except json.JSONDecodeError as e:
    logger.error(f"❌ Ошибка парсинга JSON: {e}")
    CONTENT = {}


@router.callback_query(F.data == "general_info")
async def show_general_info_menu(callback: CallbackQuery, state: FSMContext):
    """
    Показывает главное меню раздела "Общая информация".
    
    Args:
        callback: Callback от нажатия кнопки
        state: FSM контекст
    """
    await state.set_state(MenuStates.general_info)
    
    main_menu_text = CONTENT.get("main_menu", {})
    text = (
        f"<b>{main_menu_text.get('title', '🟢 Общая информация')}</b>\n\n"
        f"{main_menu_text.get('description', 'Выберите интересующий раздел:')}"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_general_info_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_general_info_menu: {e}")
        await callback.answer("Произошла ошибка. Попробуйте еще раз.")


# ========== АДРЕСА ПАРКОВ ==========

@router.callback_query(F.data == "gen_addresses")
async def show_addresses_menu(callback: CallbackQuery):
    """Показывает меню выбора парка для просмотра адреса."""
    text = (
        "<b>📍 Адреса парков</b>\n\n"
        "Выберите парк, чтобы узнать:\n"
        "• Полный адрес\n"
        "• Как добраться от метро\n"
        "• Где найти парк в ТРЦ\n"
        "• Информацию о парковке"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_parks_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_addresses_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("park_"))
async def show_park_address(callback: CallbackQuery):
    """
    Показывает адрес и информацию о конкретном парке.

    Обрабатывает callback: park_zeleno, park_kashir, park_columb
    """
    park_code = callback.data.split("_")[1]  # zeleno, kashir, columb
    # ИСПРАВЛЕНИЕ: Добавлено подробное логирование для диагностики проблемы с адресами ТРЦ
    logger.info(f"Пользователь {callback.from_user.id} запрашивает адрес парка '{park_code}'")

    addresses = CONTENT.get("addresses", {})
    park_info = addresses.get(park_code, {})

    if not park_info:
        # ИСПРАВЛЕНИЕ: Улучшенное сообщение об отсутствии информации
        logger.warning(f"⚠️ Информация о парке '{park_code}' не найдена в JSON для пользователя {callback.from_user.id}")
        logger.debug(f"Доступные парки в JSON: {list(addresses.keys())}")
        await callback.answer(
            f"Информация о выбранном ТРЦ временно недоступна. Обратитесь к администратору.",
            show_alert=True
        )
        return

    text = (
        f"<b>🏢 {park_info.get('name')}</b>\n\n"
        f"<b>📍 Адрес:</b>\n{park_info.get('full_address')}\n\n"
        f"<b>🚇 Как добраться:</b>\n{park_info.get('metro')}\n\n"
        f"<b>Маршрут:</b>\n{park_info.get('how_to_get')}\n\n"
        f"<b>🗺️ Расположение в ТРЦ:</b>\n{park_info.get('location_in_mall')}\n\n"
        f"<b>🅿️ Парковка:</b>\n{park_info.get('parking')}"
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_addresses()
        )
        await callback.answer()
        logger.info(f"✅ Адрес парка '{park_code}' успешно показан пользователю {callback.from_user.id}")
    except Exception as e:
        # ИСПРАВЛЕНИЕ: Расширенное логирование ошибок с полным traceback
        logger.error(f"❌ Ошибка в show_park_address для парка '{park_code}', пользователь {callback.from_user.id}: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки информации")


# ========== ВАЖНЫЕ ТЕЛЕФОНЫ ==========

@router.callback_query(F.data == "gen_phones")
async def show_phones_menu(callback: CallbackQuery):
    """Показывает меню выбора парка для просмотра телефонов."""
    text = (
        "<b>📞 Важные номера телефонов</b>\n\n"
        "Выберите парк, чтобы узнать контакты:\n"
        "• Администратор парка\n"
        "• Старший смены\n"
        "• Техническая поддержка\n"
        "• Экстренная связь"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_parks_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_phones_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("park_") & F.data.in_(["park_zeleno", "park_kashir", "park_columb"]))
async def show_park_phones(callback: CallbackQuery, state: FSMContext):
    """
    Показывает телефоны конкретного парка.
    
    Обрабатывает те же callback что и адреса, но проверяет текущее состояние.
    """
    # Получаем текущее состояние, чтобы понять, откуда пришел запрос
    current_state = await state.get_state()
    
    # Если мы в разделе телефонов, показываем телефоны
    # Иначе функция show_park_address обработает как адрес
    
    park_code = callback.data.split("_")[1]
    phones = CONTENT.get("phones", {})
    park_phones = phones.get(park_code, {})
    
    if not park_phones:
        await callback.answer("Информация о телефонах не найдена", show_alert=True)
        return
    
    admin = park_phones.get("admin", {})
    senior = park_phones.get("senior_shift", {})
    tech = park_phones.get("tech_support", {})
    emergency = park_phones.get("emergency", {})
    
    text = (
        f"<b>📞 {park_phones.get('park_name')}</b>\n\n"
        f"<b>👤 {admin.get('name')}:</b>\n"
        f"   {admin.get('person')}\n"
        f"   📱 <a href='tel:{admin.get('phone')}'>{admin.get('phone')}</a>\n"
        f"   ⏰ {admin.get('work_hours')}\n\n"
        f"<b>👔 {senior.get('name')}:</b>\n"
        f"   📱 <a href='tel:{senior.get('phone')}'>{senior.get('phone')}</a>\n"
        f"   ⏰ {senior.get('work_hours')}\n\n"
        f"<b>🔧 {tech.get('name')}:</b>\n"
        f"   📱 <a href='tel:{tech.get('phone')}'>{tech.get('phone')}</a>\n"
        f"   ⏰ {tech.get('work_hours')}\n\n"
        f"<b>🚨 {emergency.get('name')}:</b>\n"
        f"   📱 <a href='tel:{emergency.get('phone')}'>{emergency.get('phone')}</a>\n"
        f"   ⏰ {emergency.get('work_hours')}"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_phones(),
            disable_web_page_preview=True
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_park_phones: {e}")
        await callback.answer("Ошибка загрузки телефонов")


# ========== ВНЕШТАТНЫЕ СИТУАЦИИ ==========

@router.callback_query(F.data == "gen_emergency")
async def show_emergency_menu(callback: CallbackQuery):
    """Показывает меню внештатных ситуаций."""
    emergency_data = CONTENT.get("emergency_situations", {})
    
    text = (
        f"<b>{emergency_data.get('title', '🚨 Действия во внештатных ситуациях')}</b>\n\n"
        "Выберите тип ситуации для получения инструкций:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_emergency_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_emergency_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("emergency_"))
async def show_emergency_instruction(callback: CallbackQuery):
    """
    Показывает инструкцию по конкретной внештатной ситуации.
    
    Обрабатывает: evacuation, fire, medical, conflict, technical
    """
    situation_type = callback.data.split("_")[1]
    
    emergency_situations = CONTENT.get("emergency_situations", {})
    situation = emergency_situations.get(situation_type, {})
    
    if not situation:
        await callback.answer("Инструкция не найдена", show_alert=True)
        return
    
    title = situation.get("title", "")
    
    # Формируем текст в зависимости от типа ситуации
    if situation_type in ["evacuation", "fire", "medical", "technical"]:
        steps = situation.get("steps", [])
        text = f"<b>{title}</b>\n\n" + "\n\n".join(steps)
        
        # Добавляем дополнительную информацию если есть
        if "emergency_exits" in situation:
            text += f"\n\n{situation['emergency_exits']}"
        if "extinguisher_location" in situation:
            text += f"\n\n{situation['extinguisher_location']}"
        if "first_aid_kit" in situation:
            text += f"\n\n{situation['first_aid_kit']}"
        if "common_issues" in situation:
            text += f"\n\n{situation['common_issues']}"
            
    elif situation_type == "conflict":
        algorithm = situation.get("algorithm", [])
        phrases = situation.get("phrases", {})
        
        text = f"<b>{title}</b>\n\n" + "\n\n".join(algorithm)
        text += f"\n\n{phrases.get('good', '')}"
        text += f"\n\n{phrases.get('bad', '')}"
    else:
        text = f"<b>{title}</b>\n\nИнструкция в разработке."
    
    try:
        # Telegram ограничивает длину сообщения 4096 символов
        if len(text) > 4000:
            # Разбиваем на части
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # Последняя часть - с кнопками
                    await callback.message.answer(
                        text=part,
                        reply_markup=get_back_to_emergency()
                    )
                else:
                    await callback.message.answer(text=part)
            # Удаляем старое сообщение
            await callback.message.delete()
        else:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_emergency()
            )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_emergency_instruction: {e}")
        await callback.answer("Ошибка загрузки инструкции")


# ========== ЗАРПЛАТА И АВАНС ==========

@router.callback_query(F.data == "gen_salary")
async def show_salary_info(callback: CallbackQuery):
    """Показывает информацию о зарплате и авансе."""
    salary_data = CONTENT.get("salary_info", {})
    schedule = salary_data.get("schedule", {})
    payment_methods = salary_data.get("payment_methods", [])
    delays = salary_data.get("delays", {})
    
    text = (
        f"<b>{salary_data.get('title', '💰 Зарплата и аванс')}</b>\n\n"
        f"{schedule.get('advance', '')}\n"
        f"{schedule.get('salary', '')}\n"
        f"{schedule.get('amount', '')}\n\n"
        f"<b>💳 Способы получения:</b>\n"
    )
    
    text += "\n".join(payment_methods)
    text += f"\n\n{salary_data.get('documents', '')}"
    text += f"\n\n<b>{delays.get('title', '')}</b>\n"
    text += "\n".join(delays.get('steps', []))
    text += f"\n\n{salary_data.get('taxes', '')}"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_general_info(),
            disable_web_page_preview=True
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_salary_info: {e}")
        await callback.answer("Ошибка загрузки информации")


# ========== ПРИКАЗЫ ПАРКА ==========

@router.callback_query(F.data == "gen_orders")
async def show_orders_menu(callback: CallbackQuery):
    """Показывает меню приказов парка."""
    orders_data = CONTENT.get("orders", {})
    
    text = (
        f"<b>{orders_data.get('title', '📄 Приказы парка')}</b>\n\n"
        f"{orders_data.get('description', '')}\n\n"
        f"{orders_data.get('how_to_access', '')}\n\n"
        f"{orders_data.get('important', '')}"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_orders_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_orders_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("order_"))
async def send_order_document(callback: CallbackQuery):
    """
    Отправляет PDF-документ приказа.
    
    В реальном проекте здесь будет загрузка из content/media/documents/
    """
    order_number = callback.data.split("_")[1]
    
    # Путь к документам
    documents_path = Path(__file__).parent.parent / "content" / "media" / "documents"
    order_file = documents_path / f"order_{order_number}.pdf"
    
    try:
        if order_file.exists():
            # Отправляем реальный документ
            document = FSInputFile(order_file)
            await callback.message.answer_document(
                document=document,
                caption=f"📄 Приказ №{order_number}\n\n"
                        "⚠️ Ознакомьтесь с документом и распишитесь в журнале."
            )
            await callback.answer("Документ отправлен ✅")
        else:
            # Если файла нет - отправляем уведомление
            await callback.answer(
                f"Документ приказа №{order_number} временно недоступен. "
                "Обратитесь к администратору.",
                show_alert=True
            )
    except Exception as e:
        logger.error(f"Ошибка отправки документа order_{order_number}: {e}")
        await callback.answer("Ошибка отправки документа", show_alert=True)


# ========== СКИДКИ ПАРТНЕРОВ ==========

@router.callback_query(F.data == "gen_discounts")
async def show_discounts_menu(callback: CallbackQuery):
    """Показывает меню выбора парка для просмотра скидок."""
    discounts_data = CONTENT.get("partner_discounts", {})
    
    text = (
        f"<b>{discounts_data.get('title', '🎁 Скидки у партнеров ТРЦ')}</b>\n\n"
        f"{discounts_data.get('description', '')}\n\n"
        f"{discounts_data.get('how_to_get', '')}\n\n"
        "Выберите парк:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_discounts_parks_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_discounts_menu: {e}")
        await callback.answer("Ошибка загрузки меню")


@router.callback_query(F.data.startswith("discount_"))
async def show_park_discounts(callback: CallbackQuery):
    """Показывает скидки партнеров для конкретного парка."""
    park_code = callback.data.split("_")[1]
    
    discounts = CONTENT.get("partner_discounts", {})
    park_discounts = discounts.get(park_code, {})
    
    if not park_discounts:
        await callback.answer("Информация о скидках не найдена", show_alert=True)
        return
    
    text = f"<b>🎁 {park_discounts.get('title')}</b>\n\n"
    
    partners = park_discounts.get("partners", [])
    for partner in partners:
        text += (
            f"{partner.get('name')}\n"
            f"💰 <b>Скидка:</b> {partner.get('discount')}\n"
            f"📋 {partner.get('conditions')}\n"
            f"📍 {partner.get('location')}\n\n"
        )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_discounts()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка в show_park_discounts: {e}")
        await callback.answer("Ошибка загрузки скидок")

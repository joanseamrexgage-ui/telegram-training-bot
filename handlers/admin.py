"""
Handler для админ-панели.

Обрабатывает:
- Авторизацию по паролю
- Просмотр статистики
- Управление пользователями
- Редактирование контента
- Рассылку сообщений
"""

import hashlib
from datetime import datetime, timedelta
from typing import Dict

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter

from keyboards.admin_kb import (
    get_admin_main_menu,
    get_stats_menu,
    get_users_menu,
    get_user_actions,
    get_content_menu,
    get_broadcast_menu,
    get_broadcast_confirm,
    get_back_to_admin,
    get_cancel_button,
    get_pagination_keyboard
)
from states.admin_states import AdminStates
from database.crud import (
    get_all_users,
    get_user_by_telegram_id,
    block_user,
    unblock_user,
    get_user_activity,
    get_statistics,
    get_active_users_count,
    get_new_users_count,
    get_blocked_users,
    get_section_statistics
)
# CRIT-005 FIX: Don't load config globally
from utils.logger import logger
import os

# Создаем router для админки
router = Router(name='admin')

# CRIT-004/CRIT-005 FIX: Get admin password from environment directly
# This prevents circular imports and ensures config is loaded only once in bot.py
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Хранилище попыток ввода пароля {user_id: {"attempts": int, "blocked_until": datetime}}
password_attempts: Dict[int, dict] = {}

# Максимум попыток и время блокировки
MAX_ATTEMPTS = 3
BLOCK_DURATION = timedelta(minutes=5)


def hash_password(password: str) -> str:
    """Хеширует пароль с помощью SHA-256."""
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(input_password: str, correct_password_hash: str) -> bool:
    """Проверяет правильность введенного пароля."""
    return hash_password(input_password) == correct_password_hash


def is_user_blocked_from_attempts(user_id: int) -> bool:
    """Проверяет, заблокирован ли пользователь из-за неверных попыток."""
    if user_id not in password_attempts:
        return False
    
    blocked_until = password_attempts[user_id].get("blocked_until")
    if blocked_until and datetime.now() < blocked_until:
        return True
    
    # Если время блокировки прошло, сбрасываем счетчик
    if blocked_until and datetime.now() >= blocked_until:
        password_attempts[user_id] = {"attempts": 0, "blocked_until": None}
    
    return False


def increment_password_attempts(user_id: int) -> tuple[int, datetime | None]:
    """
    Увеличивает счетчик попыток ввода пароля.
    Возвращает (количество_попыток, время_блокировки).
    """
    if user_id not in password_attempts:
        password_attempts[user_id] = {"attempts": 0, "blocked_until": None}
    
    password_attempts[user_id]["attempts"] += 1
    attempts = password_attempts[user_id]["attempts"]
    
    # Если превышено количество попыток
    if attempts >= MAX_ATTEMPTS:
        blocked_until = datetime.now() + BLOCK_DURATION
        password_attempts[user_id]["blocked_until"] = blocked_until
        logger.warning(f"⚠️ Пользователь {user_id} заблокирован до {blocked_until} из-за неверного пароля")
        return attempts, blocked_until
    
    return attempts, None


def reset_password_attempts(user_id: int):
    """Сбрасывает счетчик попыток при успешной авторизации."""
    if user_id in password_attempts:
        password_attempts[user_id] = {"attempts": 0, "blocked_until": None}


# ========== АВТОРИЗАЦИЯ ==========

@router.callback_query(F.data == "admin")
async def request_admin_password(callback: CallbackQuery, state: FSMContext):
    """Запрашивает пароль для входа в админку."""
    user_id = callback.from_user.id
    
    # Проверяем блокировку
    if is_user_blocked_from_attempts(user_id):
        blocked_until = password_attempts[user_id]["blocked_until"]
        minutes_left = int((blocked_until - datetime.now()).total_seconds() / 60)
        
        await callback.answer(
            f"🚫 Превышено количество попыток!\n"
            f"Попробуйте через {minutes_left} минут.",
            show_alert=True
        )
        return
    
    await state.set_state(AdminStates.waiting_for_password)
    
    text = (
        "🔐 <b>Вход в админ-панель</b>\n\n"
        "Для доступа к админ-панели введите пароль.\n\n"
        "⚠️ Внимание:\n"
        f"• Максимум {MAX_ATTEMPTS} попытки\n"
        f"• При превышении - блокировка на {BLOCK_DURATION.seconds // 60} минут\n"
        "• Все попытки логируются\n\n"
        "Введите пароль:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_cancel_button()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка при запросе пароля: {e}")
        await callback.answer("Ошибка")


@router.message(StateFilter(AdminStates.waiting_for_password))
async def process_admin_password(message: Message, state: FSMContext):
    """Обрабатывает введенный пароль."""
    user_id = message.from_user.id
    input_password = message.text.strip()
    
    # Удаляем сообщение с паролем для безопасности
    try:
        await message.delete()
    except Exception:
        pass
    
    # Проверяем блокировку
    if is_user_blocked_from_attempts(user_id):
        blocked_until = password_attempts[user_id]["blocked_until"]
        minutes_left = int((blocked_until - datetime.now()).total_seconds() / 60)
        
        await message.answer(
            f"🚫 Вы заблокированы из-за множественных неверных попыток.\n"
            f"Попробуйте через {minutes_left} минут."
        )
        return
    
    # Проверяем пароль
    # CRIT-005 FIX: Use environment variable directly
    correct_password_hash = hash_password(ADMIN_PASSWORD)
    
    if check_password(input_password, correct_password_hash):
        # Пароль верный
        reset_password_attempts(user_id)
        await state.set_state(AdminStates.authorized)
        
        logger.info(f"✅ Пользователь {user_id} ({message.from_user.username}) вошел в админку")
        
        await show_admin_panel(message, state)
    else:
        # Пароль неверный
        attempts, blocked_until = increment_password_attempts(user_id)
        
        logger.warning(
            f"⚠️ Неверный пароль от {user_id} ({message.from_user.username}). "
            f"Попытка {attempts}/{MAX_ATTEMPTS}"
        )
        
        if blocked_until:
            await message.answer(
                f"❌ <b>Неверный пароль!</b>\n\n"
                f"🚫 Вы заблокированы до {blocked_until.strftime('%H:%M')} "
                f"из-за превышения лимита попыток.\n\n"
                f"⚠️ Ваши действия записаны в лог."
            )
            await state.clear()
        else:
            remaining = MAX_ATTEMPTS - attempts
            await message.answer(
                f"❌ <b>Неверный пароль!</b>\n\n"
                f"Осталось попыток: {remaining}\n\n"
                f"Введите пароль еще раз:"
            )


async def show_admin_panel(message: Message, state: FSMContext):
    """Показывает главное меню админ-панели."""
    # Получаем статистику для приветствия
    stats = await get_statistics()
    
    text = (
        "🔒 <b>Админ-панель</b>\n\n"
        f"👤 Администратор: {message.from_user.full_name}\n"
        f"🕐 Вход: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
        f"📊 <b>Быстрая статистика:</b>\n"
        f"• Всего пользователей: {stats.get('total_users', 0)}\n"
        f"• Активных сегодня: {stats.get('active_today', 0)}\n"
        f"• Новых за неделю: {stats.get('new_this_week', 0)}\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        text=text,
        reply_markup=get_admin_main_menu()
    )


@router.callback_query(F.data == "admin_panel")
async def return_to_admin_panel(callback: CallbackQuery, state: FSMContext):
    """Возвращает в главное меню админки."""
    current_state = await state.get_state()
    
    if current_state not in [
        AdminStates.authorized,
        AdminStates.stats_menu,
        AdminStates.users_menu,
        AdminStates.content_management,
        AdminStates.broadcast_menu
    ]:
        await callback.answer("Доступ запрещен", show_alert=True)
        return
    
    await state.set_state(AdminStates.authorized)
    
    stats = await get_statistics()
    
    text = (
        "🔒 <b>Админ-панель</b>\n\n"
        f"👤 Администратор: {callback.from_user.full_name}\n\n"
        f"📊 <b>Быстрая статистика:</b>\n"
        f"• Всего пользователей: {stats.get('total_users', 0)}\n"
        f"• Активных сегодня: {stats.get('active_today', 0)}\n"
        f"• Новых за неделю: {stats.get('new_this_week', 0)}\n\n"
        "Выберите действие:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка возврата в админку: {e}")
        await callback.answer("Ошибка")


@router.callback_query(F.data == "admin_logout")
async def admin_logout(callback: CallbackQuery, state: FSMContext):
    """Выход из админ-панели."""
    user_id = callback.from_user.id
    logger.info(f"👋 Пользователь {user_id} вышел из админки")
    
    await state.clear()
    
    text = (
        "👋 <b>Вы вышли из админ-панели</b>\n\n"
        "Все сессии завершены.\n"
        "Для повторного входа нужно будет снова ввести пароль."
    )
    
    try:
        await callback.message.edit_text(text=text)
        await callback.answer("Выход выполнен")
    except Exception as e:
        logger.error(f"Ошибка при выходе: {e}")
        await callback.answer("Выход выполнен")


# ========== СТАТИСТИКА ==========

@router.callback_query(F.data == "admin_stats")
async def show_stats_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает меню статистики."""
    await state.set_state(AdminStates.stats_menu)
    
    text = "📊 <b>Статистика использования</b>\n\nВыберите тип статистики:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа меню статистики: {e}")
        await callback.answer("Ошибка")


@router.callback_query(F.data == "stats_general")
async def show_general_stats(callback: CallbackQuery):
    """Показывает общую статистику."""
    stats = await get_statistics()
    
    text = (
        "📊 <b>Общая статистика</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего зарегистрировано: {stats.get('total_users', 0)}\n"
        f"• Активных сегодня: {stats.get('active_today', 0)}\n"
        f"• Активных за неделю: {stats.get('active_week', 0)}\n"
        f"• Новых за неделю: {stats.get('new_this_week', 0)}\n"
        f"• Заблокированных: {stats.get('blocked_users', 0)}\n\n"
        f"📱 <b>Активность:</b>\n"
        f"• Всего действий: {stats.get('total_actions', 0)}\n"
        f"• Действий сегодня: {stats.get('actions_today', 0)}\n"
        f"• Среднее действий/день: {stats.get('avg_actions_per_day', 0):.1f}\n\n"
        f"🕐 <b>Последнее обновление:</b>\n"
        f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа общей статистики: {e}")
        await callback.answer("Ошибка")


@router.callback_query(F.data == "stats_sections")
async def show_section_stats(callback: CallbackQuery):
    """Показывает статистику по разделам."""
    section_stats = await get_section_statistics()
    
    text = "📱 <b>Популярные разделы</b>\n\n"
    
    if section_stats:
        for i, (section, count) in enumerate(section_stats[:10], 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{emoji} {section}: {count} просмотров\n"
    else:
        text += "Данных пока нет"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа статистики разделов: {e}")
        await callback.answer("Ошибка")


# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==========

@router.callback_query(F.data == "admin_users")
async def show_users_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает меню управления пользователями."""
    await state.set_state(AdminStates.users_menu)
    
    text = "👥 <b>Управление пользователями</b>\n\nВыберите действие:"
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_users_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа меню пользователей: {e}")
        await callback.answer("Ошибка")


@router.callback_query(F.data == "users_list")
async def show_users_list(callback: CallbackQuery):
    """Показывает список всех пользователей с пагинацией."""
    users = await get_all_users()
    
    if not users:
        await callback.answer("Пользователей пока нет", show_alert=True)
        return
    
    # Пагинация: 10 пользователей на страницу
    page = 1
    per_page = 10
    total_pages = (len(users) + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_users = users[start_idx:end_idx]
    
    text = f"📋 <b>Список пользователей</b> (стр. {page}/{total_pages})\n\n"
    
    for user in page_users:
        status = "🚫" if user.get('is_blocked') else "✅"
        username = f"@{user.get('username')}" if user.get('username') else "нет username"
        
        text += (
            f"{status} <b>{user.get('first_name', 'Без имени')}</b> ({username})\n"
            f"   ID: <code>{user.get('telegram_id')}</code>\n"
            f"   Регистрация: {user.get('registration_date', 'неизвестно')}\n\n"
        )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_pagination_keyboard(page, total_pages, "users_list")
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа списка пользователей: {e}")
        await callback.answer("Ошибка")


@router.callback_query(F.data.startswith("user_block_"))
async def block_user_action(callback: CallbackQuery):
    """Блокирует пользователя."""
    user_id = int(callback.data.replace("user_block_", ""))
    
    success = await block_user(user_id)
    
    if success:
        logger.info(f"🚫 Администратор {callback.from_user.id} заблокировал пользователя {user_id}")
        await callback.answer("✅ Пользователь заблокирован", show_alert=True)
    else:
        await callback.answer("❌ Ошибка блокировки", show_alert=True)


@router.callback_query(F.data.startswith("user_unblock_"))
async def unblock_user_action(callback: CallbackQuery):
    """Разблокирует пользователя."""
    user_id = int(callback.data.replace("user_unblock_", ""))
    
    success = await unblock_user(user_id)
    
    if success:
        logger.info(f"✅ Администратор {callback.from_user.id} разблокировал пользователя {user_id}")
        await callback.answer("✅ Пользователь разблокирован", show_alert=True)
    else:
        await callback.answer("❌ Ошибка разблокировки", show_alert=True)


# ========== УПРАВЛЕНИЕ КОНТЕНТОМ ==========

@router.callback_query(F.data == "admin_content")
async def show_content_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает меню управления контентом."""
    await state.set_state(AdminStates.content_management)
    
    text = (
        "✏️ <b>Редактирование контента</b>\n\n"
        "Выберите раздел для редактирования:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_content_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа меню контента: {e}")
        await callback.answer("Ошибка")


# ========== РАССЫЛКА ==========

@router.callback_query(F.data == "admin_broadcast")
async def show_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    """Показывает меню рассылки."""
    await state.set_state(AdminStates.broadcast_menu)
    
    text = (
        "📢 <b>Рассылка сообщений</b>\n\n"
        "Выберите целевую аудиторию:"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_broadcast_menu()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка показа меню рассылки: {e}")
        await callback.answer("Ошибка")


@router.callback_query(F.data.startswith("broadcast_"))
async def process_broadcast_target(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает выбор целевой аудитории."""
    target = callback.data.replace("broadcast_", "")
    
    if target == "history":
        await callback.answer("История рассылок - в разработке", show_alert=True)
        return
    
    # Подсчитываем количество получателей
    if target == "all":
        count = await get_active_users_count()
        target_text = "всем пользователям"
    elif target == "sales":
        count = 0  # TODO: Реализовать подсчет по отделам
        target_text = "отделу продаж"
    elif target == "sport":
        count = 0
        target_text = "спортивному отделу"
    elif target == "active":
        count = await get_active_users_count()
        target_text = "активным пользователям"
    else:
        await callback.answer("Неизвестная аудитория", show_alert=True)
        return
    
    await state.update_data(broadcast_target=target, broadcast_count=count)
    await state.set_state(AdminStates.broadcast_waiting_text)
    
    text = (
        f"📢 <b>Рассылка: {target_text}</b>\n\n"
        f"Получателей: {count} чел.\n\n"
        "Введите текст сообщения для рассылки:\n\n"
        "💡 Можно использовать HTML-форматирование:\n"
        "• <code>&lt;b&gt;жирный&lt;/b&gt;</code>\n"
        "• <code>&lt;i&gt;курсив&lt;/i&gt;</code>\n"
        "• <code>&lt;code&gt;код&lt;/code&gt;</code>"
    )
    
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_cancel_button()
        )
        await callback.answer()
    except Exception as e:
        logger.error(f"Ошибка запроса текста рассылки: {e}")
        await callback.answer("Ошибка")


@router.message(StateFilter(AdminStates.broadcast_waiting_text))
async def confirm_broadcast(message: Message, state: FSMContext):
    """Подтверждение рассылки."""
    broadcast_text = message.text
    data = await state.get_data()
    
    target = data.get("broadcast_target")
    count = data.get("broadcast_count", 0)
    
    await state.update_data(broadcast_text=broadcast_text)
    await state.set_state(AdminStates.broadcast_confirm)
    
    text = (
        "📢 <b>Подтвердите рассылку</b>\n\n"
        f"Получателей: {count} чел.\n\n"
        "Текст сообщения:\n"
        "─────────\n"
        f"{broadcast_text}\n"
        "─────────\n\n"
        "⚠️ Отправить?"
    )
    
    await message.answer(
        text=text,
        reply_markup=get_broadcast_confirm(target, count)
    )


@router.callback_query(F.data.startswith("broadcast_send_"))
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    """Отправляет рассылку."""
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    target = data.get("broadcast_target")
    
    await state.set_state(AdminStates.broadcast_sending)
    
    # Получаем список получателей
    if target == "all":
        users = await get_all_users()
    elif target == "active":
        users = await get_all_users()  # TODO: фильтровать активных
    else:
        users = []
    
    # Отправляем рассылку
    success_count = 0
    fail_count = 0
    
    await callback.message.edit_text("📤 Рассылка начата...")
    
    for user in users:
        if user.get('is_blocked'):
            continue
        
        try:
            await callback.bot.send_message(
                chat_id=user.get('telegram_id'),
                text=f"📢 <b>Объявление от администрации</b>\n\n{broadcast_text}"
            )
            success_count += 1
        except Exception as e:
            logger.error(f"Ошибка отправки пользователю {user.get('telegram_id')}: {e}")
            fail_count += 1
    
    logger.info(
        f"📢 Администратор {callback.from_user.id} отправил рассылку. "
        f"Успешно: {success_count}, Ошибок: {fail_count}"
    )
    
    result_text = (
        "✅ <b>Рассылка завершена</b>\n\n"
        f"Успешно отправлено: {success_count}\n"
        f"Ошибок: {fail_count}"
    )
    
    await callback.message.edit_text(
        text=result_text,
        reply_markup=get_back_to_admin()
    )
    await state.set_state(AdminStates.authorized)


# ========== ЛОГИ ==========

@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery):
    """Показывает последние логи."""
    # TODO: Реализовать чтение логов из файла
    await callback.answer("Просмотр логов - в разработке", show_alert=True)

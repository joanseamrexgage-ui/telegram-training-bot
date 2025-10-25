"""
Handler для админ-панели.

Обрабатывает:
- Авторизацию по паролю
- Просмотр статистики
- Управление пользователями
- Редактирование контента
- Рассылку сообщений
"""

import csv
import hashlib  # Deprecated: kept for backward compatibility
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict

# SEC-001 FIX: bcrypt for secure password hashing
import bcrypt

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, FSInputFile
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
    get_section_statistics,
    get_recent_activity,
    get_all_activity_for_export,
    get_date_statistics,
    get_users_for_export
)
# CRIT-005 FIX: Don't load config globally
from utils.logger import logger
from utils.timezone import get_msk_now, format_msk_datetime
# BLOCKER-002 FIX: Redis-backed password attempt tracking
from utils.auth_security import get_auth_security, MAX_ATTEMPTS, BLOCK_DURATION_MINUTES
# HIGH-003 FIX: Input sanitization and HTML escaping
from utils.sanitize import (
    sanitize_user_input,
    sanitize_username,
    sanitize_broadcast_message,
    sanitize_search_query,
    safe_user_name,
    safe_username
)
import os

# Создаем router для админки
router = Router(name='admin')

# SEC-001 FIX: bcrypt password hash from .env
# ⚠️ MIGRATION NOTE: Old SHA-256 hashes still supported for backward compatibility
# Generate new hash: python generate_admin_hash.py
# OLD SHA-256 default (admin123): "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"
# NEW bcrypt default (admin123): "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5ViT8QJy4E6M6"
DEFAULT_ADMIN_HASH = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5ViT8QJy4E6M6"  # bcrypt: admin123
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", DEFAULT_ADMIN_HASH)

# BLOCKER-002 FIX: Password attempts now tracked in Redis via utils.auth_security
# Removed in-memory password_attempts dict - now persists across bot restarts
# Maximum attempts and block duration configured in utils.auth_security:
# - MAX_ATTEMPTS = 3
# - BLOCK_DURATION_MINUTES = 5


def hash_password(password: str) -> str:
    """
    Deprecated: Хеширует пароль с помощью SHA-256

    SEC-001: Use bcrypt instead. This function kept for backward compatibility only.
    """
    return hashlib.sha256(password.encode()).hexdigest()


def check_password(input_password: str, correct_password_hash: str) -> bool:
    """
    Проверяет правильность введенного пароля

    SEC-001 FIX: Supports both bcrypt (new) and SHA-256 (legacy)

    Args:
        input_password: Пароль в открытом виде
        correct_password_hash: Хеш из .env (bcrypt или SHA-256)

    Returns:
        True if password matches, False otherwise
    """
    # SEC-001: Check if hash is bcrypt format
    if correct_password_hash.startswith("$2b$") or correct_password_hash.startswith("$2a$"):
        # New bcrypt verification (secure)
        try:
            return bcrypt.checkpw(
                input_password.encode('utf-8'),
                correct_password_hash.encode('utf-8')
            )
        except Exception as e:
            logger.error(f"bcrypt verification error: {e}")
            return False
    else:
        # Legacy SHA-256 verification (insecure, backward compatibility)
        logger.warning(
            "⚠️ SECURITY WARNING: Using legacy SHA-256 password hash! "
            "Please regenerate with bcrypt: python generate_admin_hash.py"
        )
        return hash_password(input_password) == correct_password_hash


# BLOCKER-002 FIX: Redis-backed password attempt tracking
# These functions now use utils.auth_security for persistent storage


async def is_user_blocked_from_attempts(user_id: int) -> tuple[bool, datetime | None]:
    """
    Проверяет, заблокирован ли пользователь из-за неверных попыток.

    BLOCKER-002 FIX: Now uses Redis-backed storage (persists across restarts)

    Returns:
        Tuple of (is_blocked, blocked_until_datetime)
    """
    auth_security = get_auth_security()
    if not auth_security:
        logger.error("❌ AuthSecurity not initialized, blocking access as safety measure")
        return True, None

    is_blocked, blocked_until = await auth_security.is_user_blocked(user_id)
    return is_blocked, blocked_until


async def increment_password_attempts(user_id: int) -> tuple[int, datetime | None]:
    """
    Увеличивает счетчик попыток ввода пароля.

    BLOCKER-002 FIX: Now uses Redis-backed storage (persists across restarts)

    Returns:
        Tuple of (attempt_count, blocked_until_datetime)
    """
    auth_security = get_auth_security()
    if not auth_security:
        logger.error("❌ AuthSecurity not initialized, cannot track attempts")
        return 0, None

    attempts, blocked_until = await auth_security.increment_password_attempts(user_id)
    return attempts, blocked_until


async def reset_password_attempts(user_id: int):
    """
    Сбрасывает счетчик попыток при успешной авторизации.

    BLOCKER-002 FIX: Now uses Redis-backed storage (persists across restarts)
    """
    auth_security = get_auth_security()
    if not auth_security:
        logger.error("❌ AuthSecurity not initialized, cannot reset attempts")
        return

    await auth_security.reset_password_attempts(user_id)


# ========== АВТОРИЗАЦИЯ ==========

@router.callback_query(F.data == "admin")
async def request_admin_password(callback: CallbackQuery, state: FSMContext):
    """Запрашивает пароль для входа в админку."""
    user_id = callback.from_user.id

    # BLOCKER-002 FIX: Check Redis-backed block status
    is_blocked, blocked_until = await is_user_blocked_from_attempts(user_id)
    if is_blocked and blocked_until:
        minutes_left = int((blocked_until - datetime.utcnow()).total_seconds() / 60)

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
        f"• При превышении - блокировка на {BLOCK_DURATION_MINUTES} минут\n"
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


@router.callback_query(F.data == "cancel_admin_action")
async def cancel_admin_action(callback: CallbackQuery, state: FSMContext):
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Обработчик кнопки "Отменить" при входе в админ-панель.

    Ранее кнопка "Отменить" использовала callback_data="admin_panel", что вызывало ошибку,
    т.к. обработчик return_to_admin_panel проверял авторизацию и отказывал в доступе.

    Теперь этот обработчик:
    - Сбрасывает любые FSM состояния через state.clear()
    - Возвращает пользователя в главное меню
    - Логирует событие отмены
    - Не выдает ошибок даже если FSM уже сброшен
    """
    try:
        user_id = callback.from_user.id
        current_state = await state.get_state()

        # Логируем отмену входа в админку
        logger.info(
            f"👤 Пользователь {user_id} (@{callback.from_user.username}) "
            f"отменил вход в админ-панель из состояния: {current_state}"
        )

        # Сбрасываем FSM состояние (безопасно даже если уже сброшено)
        await state.clear()

        # Импортируем константы для главного меню
        from handlers.start import RETURN_TEXT
        from keyboards.inline import get_main_menu_keyboard

        # Возвращаем в главное меню
        await callback.message.edit_text(
            text=RETURN_TEXT,
            reply_markup=get_main_menu_keyboard()
        )

        # Отвечаем на callback
        await callback.answer("❌ Вход в админ-панель отменен")

        logger.info(f"✅ Пользователь {user_id} успешно вернулся в главное меню после отмены")

    except Exception as e:
        # ИСПРАВЛЕНИЕ: Расширенное логирование ошибок с полным traceback
        logger.error(
            f"❌ Ошибка при отмене входа в админку для пользователя {callback.from_user.id}: {e}",
            exc_info=True
        )
        # Даже при ошибке пытаемся уведомить пользователя
        try:
            await callback.answer("Вход отменен", show_alert=False)
        except Exception:
            pass


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

    # BLOCKER-002 FIX: Check Redis-backed block status
    is_blocked, blocked_until = await is_user_blocked_from_attempts(user_id)
    if is_blocked and blocked_until:
        minutes_left = int((blocked_until - datetime.utcnow()).total_seconds() / 60)

        await message.answer(
            f"🚫 Вы заблокированы из-за множественных неверных попыток.\n"
            f"Попробуйте через {minutes_left} минут."
        )
        return

    # Проверяем пароль
    # Сравниваем хеш введенного пароля с хешем из .env
    if check_password(input_password, ADMIN_PASS_HASH):
        # ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлен try-except блок для обработки ошибок
        # Ранее при любой ошибке в show_admin_panel пользователь получал необработанное исключение
        try:
            # BLOCKER-002 FIX: Reset attempts in Redis
            await reset_password_attempts(user_id)
            await state.set_state(AdminStates.authorized)

            logger.info(f"✅ Пользователь {user_id} (@{message.from_user.username}) успешно авторизован в админке")

            # Показываем админ-панель
            await show_admin_panel(message, state)

            logger.info(f"✅ Админ-панель успешно показана пользователю {user_id}")

        except Exception as e:
            # ИСПРАВЛЕНИЕ: Полное логирование ошибок с traceback
            logger.error(
                f"❌ Критическая ошибка при входе в админку для пользователя {user_id}: {e}",
                exc_info=True
            )
            # Уведомляем пользователя о проблеме
            try:
                await message.answer(
                    "❌ <b>Произошла ошибка при входе в админ-панель</b>\n\n"
                    "Пароль верный, но возникла техническая проблема.\n"
                    "Обратитесь к системному администратору.\n\n"
                    f"Код ошибки: {type(e).__name__}"
                )
            except Exception:
                pass
            # Сбрасываем состояние при ошибке
            await state.clear()
    else:
        # BLOCKER-002 FIX: Increment attempts in Redis
        attempts, blocked_until = await increment_password_attempts(user_id)

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
    """
    Показывает главное меню админ-панели.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлена полная обработка ошибок.
    Ранее любая ошибка при получении статистики или отправке сообщения
    приводила к необработанному исключению и сообщению "Произошла ошибка. Попробуйте позже."
    """
    try:
        # Логируем попытку показа админ-панели
        logger.info(f"🔒 Загрузка админ-панели для пользователя {message.from_user.id}")

        # Получаем статистику для приветствия
        try:
            stats = await get_statistics()
            logger.info(f"✅ Статистика загружена успешно")
        except Exception as stats_error:
            # Если ошибка при получении статистики - используем заглушку
            logger.error(f"⚠️ Ошибка при загрузке статистики: {stats_error}", exc_info=True)
            stats = {
                'total_users': 0,
                'active_today': 0,
                'new_this_week': 0
            }

        # HIGH-003 FIX: Sanitize admin name
        admin_name = safe_user_name(message.from_user)

        text = (
            "🔒 <b>Админ-панель</b>\n\n"
            f"👤 Администратор: {admin_name}\n"
            # TIMEZONE: Используем московское время для отображения
            f"🕐 Вход: {get_msk_now().strftime('%d.%m.%Y %H:%M')} (МСК)\n\n"
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

        logger.info(f"✅ Админ-панель успешно отправлена пользователю {message.from_user.id}")

    except Exception as e:
        # ИСПРАВЛЕНИЕ: Полное логирование всех ошибок с traceback
        logger.error(
            f"❌ Критическая ошибка в show_admin_panel для пользователя {message.from_user.id}: {e}",
            exc_info=True
        )
        # Пробрасываем исключение выше для обработки в process_admin_password
        raise


@router.callback_query(F.data == "admin_panel")
async def return_to_admin_panel(callback: CallbackQuery, state: FSMContext):
    """
    Возвращает в главное меню админки.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #3: Расширен список разрешенных состояний.
    Ранее проверка авторизации была слишком строгой и не учитывала вложенные состояния
    админ-панели (например, broadcast_waiting_text, broadcast_confirm, broadcast_sending),
    что вызывало ошибку "Доступ запрещен" при нажатии "Назад к админке" из этих разделов.

    Теперь проверяется, что состояние начинается с "AdminStates:" - это означает,
    что пользователь уже авторизован и может вернуться в главное меню админки.
    """
    current_state = await state.get_state()

    # ИСПРАВЛЕНИЕ: Проверяем, что пользователь в любом админском состоянии
    # вместо жесткого списка конкретных состояний
    if current_state and not current_state.startswith("AdminStates:"):
        logger.warning(
            f"⚠️ Пользователь {callback.from_user.id} пытается войти в админку из состояния {current_state}"
        )
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    logger.info(f"🔙 Пользователь {callback.from_user.id} возвращается в главное меню админки")

    await state.set_state(AdminStates.authorized)

    try:
        stats = await get_statistics()
    except Exception as stats_error:
        logger.error(f"❌ Ошибка при получении статистики: {stats_error}", exc_info=True)
        stats = {'total_users': 0, 'active_today': 0, 'new_this_week': 0}
    
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


@router.callback_query(F.data == "return_to_admin")
async def return_to_admin_from_logs(callback: CallbackQuery, state: FSMContext):
    """
    ИСПРАВЛЕНИЕ БАГА: Обработчик для кнопки "Назад к админке" из раздела логов.

    Проблема: В разделе "Логи активности" использовался callback_data="return_to_admin",
    но обработчик для этого callback отсутствовал, что приводило к зависанию интерфейса.

    Решение: Добавлен отдельный обработчик, который:
    - Очищает состояние FSM
    - Возвращает пользователя в главное меню админки
    - Добавляет логирование для отладки
    - Обрабатывает ошибки с try-except
    """
    logger.info(f"🔙 Пользователь {callback.from_user.id} возвращается из логов в главное меню админки")

    try:
        # Сбрасываем состояние на authorized
        await state.set_state(AdminStates.authorized)

        # Получаем статистику
        try:
            stats = await get_statistics()
        except Exception as stats_error:
            logger.error(f"❌ Ошибка при получении статистики: {stats_error}", exc_info=True)
            stats = {'total_users': 0, 'active_today': 0, 'new_this_week': 0}

        text = (
            "🔒 <b>Админ-панель</b>\n\n"
            f"👤 Администратор: {callback.from_user.full_name}\n\n"
            f"📊 <b>Быстрая статистика:</b>\n"
            f"• Всего пользователей: {stats.get('total_users', 0)}\n"
            f"• Активных сегодня: {stats.get('active_today', 0)}\n"
            f"• Новых за неделю: {stats.get('new_this_week', 0)}\n\n"
            "Выберите действие:"
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_main_menu()
        )
        await callback.answer()
        logger.info(f"✅ Пользователь успешно вернулся в главное меню")

    except Exception as e:
        logger.error(f"❌ Ошибка при возврате в админку из логов: {e}", exc_info=True)
        await callback.answer("Ошибка возврата в меню", show_alert=True)


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
    """
    Показывает общую статистику.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #2: Добавлена обработка ошибок при получении статистики.
    Ранее при ошибке get_statistics() (из-за отсутствия get_db_session) обработчик падал
    с необработанным исключением, что вызывало сообщение "Произошла непредвиденная ошибка".
    """
    try:
        # Логируем запрос статистики
        logger.info(f"📊 Пользователь {callback.from_user.id} запросил общую статистику")

        # Получаем статистику с обработкой ошибок
        try:
            stats = await get_statistics()
            logger.info(f"✅ Общая статистика получена успешно")
        except Exception as stats_error:
            # Если ошибка при получении статистики - используем заглушку и логируем
            logger.error(
                f"❌ Ошибка при получении статистики: {stats_error}",
                exc_info=True
            )
            stats = {
                'total_users': 0,
                'active_today': 0,
                'active_week': 0,
                'new_this_week': 0,
                'blocked_users': 0,
                'total_actions': 0,
                'actions_today': 0,
                'avg_actions_per_day': 0.0
            }
            # Уведомляем пользователя об ошибке
            await callback.answer(
                "⚠️ Ошибка загрузки статистики. Показаны нулевые значения.",
                show_alert=True
            )

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
            # TIMEZONE: Время обновления отображается в МСК
            f"🕐 <b>Последнее обновление:</b>\n"
            f"{get_msk_now().strftime('%d.%m.%Y %H:%M:%S')} (МСК)"
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()

    except Exception as e:
        # ИСПРАВЛЕНИЕ: Полное логирование ошибок с traceback
        logger.error(
            f"❌ Критическая ошибка в show_general_stats для пользователя {callback.from_user.id}: {e}",
            exc_info=True
        )
        await callback.answer("Ошибка загрузки статистики", show_alert=True)


@router.callback_query(F.data == "stats_sections")
async def show_section_stats(callback: CallbackQuery):
    """
    Показывает статистику по разделам (популярные разделы).

    MVP FEATURE: Теперь показывает реальные данные за последние 7 дней.
    ИСПРАВЛЕНИЕ: Изменен статус с "В разработке" на рабочий.
    """
    # MVP: Маппинг технических названий разделов на человекочитаемые
    SECTION_NAMES = {
        "general_info": "📗 Общая информация",
        "sales": "💼 Отдел продаж",
        "sport": "⚽ Спортивный отдел",
        "admin": "⚙️ Админ-панель",
        "tests": "📝 Тесты",
        "main_menu": "🏠 Главное меню",
        None: "Без раздела"
    }

    try:
        logger.info(f"📊 Пользователь {callback.from_user.id} запросил топ популярных разделов")

        try:
            # MVP: Получаем статистику за последние 7 дней (как требовал пользователь)
            section_stats = await get_section_statistics(days=7)
            logger.info(f"✅ Получено {len(section_stats)} разделов со статистикой")

            # Дополнительное логирование для отладки
            if section_stats:
                logger.debug(f"Топ-3 раздела: {section_stats[:3]}")

        except Exception as stats_error:
            logger.error(
                f"❌ Ошибка при получении статистики разделов: {stats_error}",
                exc_info=True
            )
            section_stats = []
            await callback.answer(
                "⚠️ Ошибка загрузки статистики разделов",
                show_alert=True
            )

        # MVP: Формируем красивый вывод
        text = "📊 <b>Топ-5 разделов за 7 дней</b>\n\n"

        if section_stats:
            # Ограничиваем топ-5, как просил пользователь
            for i, (section, count) in enumerate(section_stats[:5], 1):
                # Определяем эмодзи для топ-3
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."

                # Получаем человекочитаемое название раздела
                section_name = SECTION_NAMES.get(section, f"❓ {section}")

                # MVP: Форматируем вывод как просил пользователь
                text += f"{emoji} {section_name} — {count} посещений\n"

            # Добавляем общую информацию
            total_views = sum(count for _, count in section_stats)
            text += f"\n📈 <b>Всего просмотров:</b> {total_views}"
        else:
            # MVP: Информативное сообщение вместо "Данных пока нет"
            text += (
                "Данных пока нет. Сбор статистики начат.\n\n"
                "ℹ️ Статистика собирается автоматически при переходах пользователей по разделам.\n\n"
                "Данные появятся после первых посещений разделов бота."
            )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в show_section_stats: {e}",
            exc_info=True
        )
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data == "stats_users")
async def show_users_stats(callback: CallbackQuery):
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлен обработчик для "Статистика пользователей".

    Ранее при нажатии на эту кнопку отсутствовал обработчик, что приводило
    к бесконечному "думанию" бота без ответа.

    Теперь обработчик быстро отвечает с информативным сообщением.
    """
    try:
        logger.info(f"👤 Пользователь {callback.from_user.id} запросил статистику пользователей")

        try:
            # Получаем базовую статистику
            stats = await get_statistics()

            text = (
                "👤 <b>Статистика пользователей</b>\n\n"
                f"📊 <b>Общие показатели:</b>\n"
                f"• Всего зарегистрировано: {stats.get('total_users', 0)}\n"
                f"• Активных сегодня: {stats.get('active_today', 0)}\n"
                f"• Активных за неделю: {stats.get('active_week', 0)}\n"
                f"• Новых за неделю: {stats.get('new_this_week', 0)}\n"
                f"• Заблокированных: {stats.get('blocked_users', 0)}\n\n"
                f"📈 <b>Вовлеченность:</b>\n"
                f"• Активность сегодня: {(stats.get('active_today', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%\n"
                f"• Активность за неделю: {(stats.get('active_week', 0) / max(stats.get('total_users', 1), 1) * 100):.1f}%\n\n"
                f"💡 <b>Подробная статистика по пользователям:</b>\n"
                f"Используйте раздел \"Управление пользователями\" → \"Список всех пользователей\"\n\n"
                # TIMEZONE: Время обновления в МСК
                f"🕐 Обновлено: {get_msk_now().strftime('%H:%M:%S')} (МСК)"
            )

            logger.info(f"✅ Статистика пользователей успешно сформирована")

        except Exception as stats_error:
            logger.error(f"❌ Ошибка при получении статистики пользователей: {stats_error}", exc_info=True)
            text = (
                "👤 <b>Статистика пользователей</b>\n\n"
                "⚠️ Временно недоступна из-за технической ошибки.\n\n"
                "Обратитесь к системному администратору."
            )
            await callback.answer("⚠️ Ошибка загрузки статистики", show_alert=True)

        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"❌ Критическая ошибка в show_users_stats: {e}", exc_info=True)
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data == "stats_dates")
async def show_dates_stats(callback: CallbackQuery):
    """
    MVP FEATURE: Полноценная реализация статистики по датам.

    ИСПРАВЛЕНИЕ: Изменен статус с "В разработке" на рабочий.

    Показывает:
    - Статистику по дням недели (Пн-Вс)
    - Топ-5 самых активных дней
    - Пиковые часы (топ-3)
    - Уникальные пользователи и действия
    """
    try:
        logger.info(f"📅 Пользователь {callback.from_user.id} запросил статистику по датам")

        # MVP: Получаем статистику за последние 30 дней
        stats = await get_date_statistics(days=30)

        if not stats.get("has_data"):
            text = (
                "📅 <b>Статистика по датам</b>\n\n"
                "📊 Данных пока нет.\n\n"
                "Статистика собирается автоматически при использовании бота.\n"
                "Начните использовать различные разделы, и данные появятся здесь."
            )
            logger.info(f"ℹ️ Нет данных для статистики по датам")
        else:
            # MVP: Формируем красивый вывод
            # TIMEZONE: Все данные статистики рассчитаны по московскому времени
            text = f"📅 <b>Статистика за {stats['days_analyzed']} дней (МСК)</b>\n\n"

            # Общая информация
            text += (
                f"📊 <b>Общие показатели:</b>\n"
                f"• Всего действий: {stats['total_actions']}\n"
                f"• Уникальных пользователей: {stats['unique_users']}\n"
                f"• Среднее действий/день: {stats['total_actions'] // stats['days_analyzed']}\n\n"
            )

            # Статистика по дням недели
            text += "📆 <b>По дням недели:</b>\n"
            weekday_stats = stats.get("weekday_stats", [])
            for day_stat in weekday_stats:
                if day_stat["actions"] > 0:
                    text += (
                        f"{day_stat['weekday']}: {day_stat['actions']} действий "
                        f"({day_stat['unique_users']} польз.)\n"
                    )
            text += "\n"

            # Топ-5 самых активных дней
            top_days = stats.get("top_days", [])
            if top_days:
                text += "🏆 <b>Топ-5 активных дней:</b>\n"
                for i, day in enumerate(top_days, 1):
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    date_obj = datetime.strptime(day["date"], "%Y-%m-%d")
                    date_formatted = date_obj.strftime("%d.%m.%Y")
                    text += (
                        f"{emoji} {date_formatted}: {day['actions']} действий "
                        f"({day['unique_users']} польз.)\n"
                    )
                text += "\n"

            # Пиковые часы
            # TIMEZONE: Часы отображаются по московскому времени
            top_hours = stats.get("top_hours", [])
            if top_hours:
                text += "⏰ <b>Пиковые часы (МСК):</b>\n"
                for i, hour_stat in enumerate(top_hours, 1):
                    hour = hour_stat["hour"]
                    text += (
                        f"{i}. {hour:02d}:00-{hour:02d}:59 — "
                        f"{hour_stat['actions']} действий\n"
                    )

            logger.info(f"✅ Статистика по датам успешно сформирована")

        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"❌ Ошибка в show_dates_stats: {e}", exc_info=True)
        await callback.answer("Ошибка загрузки статистики", show_alert=True)


@router.callback_query(F.data == "stats_export")
async def export_stats_to_excel(callback: CallbackQuery):
    """
    MVP FEATURE: Полноценная реализация экспорта пользователей в CSV/Excel.

    ИСПРАВЛЕНИЕ: Изменен статус с "В разработке" на рабочий.

    Экспортирует список пользователей с данными:
    - Telegram ID, username, имя, фамилия, телефон
    - Дата регистрации, последняя активность
    - Статус блокировки, права администратора
    """
    try:
        logger.info(f"📊 Пользователь {callback.from_user.id} запросил экспорт пользователей")

        # Отправляем уведомление о начале экспорта
        await callback.answer("⏳ Формирую файл...", show_alert=False)

        # MVP: Получаем данные пользователей
        users_data = await get_users_for_export()

        if not users_data:
            text = (
                "📊 <b>Экспорт пользователей</b>\n\n"
                "⚠️ В базе данных пока нет пользователей для экспорта.\n\n"
                "Данные появятся после того, как пользователи начнут использовать бота."
            )
            await callback.message.edit_text(
                text=text,
                reply_markup=get_stats_menu()
            )
            logger.info(f"ℹ️ Нет пользователей для экспорта")
            return

        # MVP: Создаем CSV файл
        # TIMEZONE: Используем московское время для имени файла
        timestamp = get_msk_now().strftime("%Y%m%d_%H%M%S")
        filename = f"users_export_{timestamp}.csv"

        # Формируем CSV содержимое
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8-sig', suffix='.csv', delete=False, newline='') as f:
            # CSV writer с правильными настройками для Excel
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "ID", "Telegram ID", "Username", "Имя", "Фамилия", "Телефон",
                    "Дата регистрации", "Последняя активность", "Заблокирован", "Администратор"
                ],
                delimiter=';'  # Для лучшей совместимости с Excel
            )

            # Заголовок
            writer.writeheader()

            # Данные
            for user in users_data:
                writer.writerow({
                    "ID": user["id"],
                    "Telegram ID": user["telegram_id"],
                    "Username": user["username"] if user["username"] else "-",
                    "Имя": user["first_name"] if user["first_name"] else "-",
                    "Фамилия": user["last_name"] if user["last_name"] else "-",
                    "Телефон": user["phone"] if user["phone"] else "-",
                    "Дата регистрации": user["registration_date"] if user["registration_date"] else "-",
                    "Последняя активность": user["last_activity"] if user["last_activity"] else "-",
                    "Заблокирован": user["is_blocked"],
                    "Администратор": user["is_admin"]
                })

            temp_path = f.name

        logger.info(f"✅ CSV файл создан: {temp_path}, записей: {len(users_data)}")

        # Отправляем файл
        document = FSInputFile(temp_path, filename=filename)

        # TIMEZONE: Время генерации в МСК
        caption = (
            f"📊 <b>Экспорт пользователей</b>\n\n"
            f"📁 Файл: <code>{filename}</code>\n"
            f"👥 Пользователей: {len(users_data)}\n"
            f"📅 Сгенерировано: {get_msk_now().strftime('%d.%m.%Y %H:%M:%S')} (МСК)\n\n"
            f"💡 Откройте файл в Excel для просмотра"
        )

        await callback.message.answer_document(
            document=document,
            caption=caption
        )

        # Удаляем временный файл
        Path(temp_path).unlink(missing_ok=True)
        logger.info(f"✅ Файл отправлен и удален: {temp_path}")

        # Возвращаем в меню статистики
        text = (
            "✅ <b>Экспорт завершен!</b>\n\n"
            "Файл с данными пользователей отправлен выше.\n\n"
            "📊 Выберите другую статистику или вернитесь в главное меню."
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )

    except Exception as e:
        logger.error(f"❌ Ошибка при экспорте пользователей: {e}", exc_info=True)
        await callback.answer("Ошибка при экспорте", show_alert=True)
        try:
            await callback.message.edit_text(
                text=(
                    "❌ <b>Ошибка экспорта</b>\n\n"
                    "Произошла ошибка при создании файла.\n"
                    "Попробуйте позже или обратитесь к администратору."
                ),
                reply_markup=get_stats_menu()
            )
        except:
            pass


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
    """
    Показывает список всех пользователей с пагинацией.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #2: Добавлена обработка ошибок при получении пользователей.
    """
    try:
        logger.info(f"👥 Пользователь {callback.from_user.id} запросил список пользователей")

        try:
            users = await get_all_users()
            logger.info(f"✅ Получено {len(users) if users else 0} пользователей")
        except Exception as users_error:
            logger.error(
                f"❌ Ошибка при получении списка пользователей: {users_error}",
                exc_info=True
            )
            await callback.answer(
                "Ошибка загрузки списка пользователей",
                show_alert=True
            )
            return

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

            # HIGH-003 FIX: Sanitize user data before display
            first_name = sanitize_user_input(user.get('first_name') or 'Без имени', max_length=50)
            username_raw = user.get('username')
            if username_raw:
                username = f"@{sanitize_username(username_raw)}"
            else:
                username = "нет username"

            text += (
                f"{status} <b>{first_name}</b> ({username})\n"
                f"   ID: <code>{user.get('telegram_id')}</code>\n"
                f"   Регистрация: {user.get('registration_date_str', 'неизвестно')}\n\n"
            )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_pagination_keyboard(page, total_pages, "users_list")
        )
        await callback.answer()

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в show_users_list: {e}",
            exc_info=True
        )
        await callback.answer("Ошибка показа списка", show_alert=True)


@router.callback_query(F.data.startswith("users_list_page_"))
async def handle_users_list_pagination(callback: CallbackQuery):
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #2: Обработчик пагинации для списка пользователей.

    Проблема: При нажатии на кнопки "Вперёд"/"Назад" в списке пользователей бот зависал,
    так как обработчик для callback_data "users_list_page_*" полностью отсутствовал.

    Решение: Добавлен полноценный обработчик с логированием и корректной обработкой страниц.
    """
    try:
        # Извлекаем номер страницы из callback_data
        page = int(callback.data.split("_")[-1])
        logger.info(f"📄 Пользователь {callback.from_user.id} запросил страницу {page} списка пользователей")

        # Получаем список пользователей
        try:
            users = await get_all_users()
            logger.info(f"✅ Получено {len(users) if users else 0} пользователей для пагинации")
        except Exception as users_error:
            logger.error(
                f"❌ Ошибка при получении списка пользователей для пагинации: {users_error}",
                exc_info=True
            )
            await callback.answer(
                "❌ Ошибка загрузки списка пользователей",
                show_alert=True
            )
            return

        if not users:
            await callback.answer("Пользователей пока нет", show_alert=True)
            return

        # Настройки пагинации
        per_page = 10
        total_pages = (len(users) + per_page - 1) // per_page

        # Проверяем корректность номера страницы
        if page < 1 or page > total_pages:
            logger.warning(f"⚠️ Запрошена некорректная страница: {page} (доступно: 1-{total_pages})")
            await callback.answer(
                f"Страница {page} не существует",
                show_alert=True
            )
            return

        # Вычисляем диапазон пользователей для текущей страницы
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_users = users[start_idx:end_idx]

        logger.info(f"📊 Страница {page}/{total_pages}: отображение пользователей {start_idx+1}-{min(end_idx, len(users))} из {len(users)}")

        # Формируем текст со списком пользователей на странице
        text = f"📋 <b>Список пользователей</b> (стр. {page}/{total_pages})\n\n"

        for user in page_users:
            status = "🚫" if user.get('is_blocked') else "✅"

            # HIGH-003 FIX: Sanitize user data before display
            first_name = sanitize_user_input(user.get('first_name') or 'Без имени', max_length=50)
            username_raw = user.get('username')
            if username_raw:
                username = f"@{sanitize_username(username_raw)}"
            else:
                username = "нет username"

            text += (
                f"{status} <b>{first_name}</b> ({username})\n"
                f"   ID: <code>{user.get('telegram_id')}</code>\n"
                f"   Регистрация: {user.get('registration_date_str', 'неизвестно')}\n\n"
            )

        # Обновляем сообщение с новой страницей
        await callback.message.edit_text(
            text=text,
            reply_markup=get_pagination_keyboard(page, total_pages, "users_list")
        )
        await callback.answer()
        logger.info(f"✅ Страница {page} списка пользователей успешно отображена для администратора {callback.from_user.id}")

    except ValueError as ve:
        logger.error(f"❌ Ошибка парсинга номера страницы из {callback.data}: {ve}")
        await callback.answer("❌ Некорректный номер страницы", show_alert=True)
    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в handle_users_list_pagination: {e}",
            exc_info=True
        )
        await callback.answer("❌ Ошибка переключения страницы", show_alert=True)


# ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлены недостающие обработчики для кнопок управления пользователями
# Проблема: При нажатии на кнопки "Поиск пользователя", "Заблокированные", "Активные сегодня", "Новые пользователи"
# интерфейс бесконечно "думал" - обработчики полностью отсутствовали

@router.callback_query(F.data == "users_search")
async def handle_users_search(callback: CallbackQuery, state: FSMContext):
    """
    Обработчик кнопки "Поиск пользователя".

    ИСПРАВЛЕНИЕ: Добавлен полностью отсутствующий обработчик.
    """
    try:
        logger.info(f"🔍 Пользователь {callback.from_user.id} запросил поиск пользователя")

        # Устанавливаем состояние ожидания ввода для поиска
        await state.set_state(AdminStates.waiting_user_search)

        text = (
            "🔍 <b>Поиск пользователя</b>\n\n"
            "Введите Telegram ID, username или имя пользователя для поиска:\n\n"
            "Примеры:\n"
            "• <code>123456789</code> (Telegram ID)\n"
            "• <code>@username</code>\n"
            "• <code>Иван</code> (имя)"
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_users_menu()  # Кнопка "Назад к управлению пользователями"
        )
        await callback.answer()
        logger.info(f"✅ Отображено меню поиска пользователя для администратора {callback.from_user.id}")

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в handle_users_search: {e}",
            exc_info=True
        )
        await callback.answer("❌ Ошибка открытия поиска", show_alert=True)


@router.callback_query(F.data == "users_blocked")
async def handle_users_blocked(callback: CallbackQuery):
    """
    Обработчик кнопки "Заблокированные пользователи".

    ИСПРАВЛЕНИЕ: Добавлен полностью отсутствующий обработчик.
    Получает список заблокированных пользователей из БД и отображает их.
    """
    try:
        logger.info(f"🚫 Пользователь {callback.from_user.id} запросил список заблокированных пользователей")

        try:
            # Получаем заблокированных пользователей из БД
            blocked_users = await get_blocked_users()
            logger.info(f"📊 Получено {len(blocked_users) if blocked_users else 0} заблокированных пользователей")
        except Exception as db_error:
            logger.error(
                f"❌ Ошибка при получении заблокированных пользователей из БД: {db_error}",
                exc_info=True
            )
            await callback.answer(
                "❌ Ошибка загрузки данных из базы",
                show_alert=True
            )
            return

        if not blocked_users:
            logger.info("ℹ️ Заблокированных пользователей не найдено")
            await callback.answer(
                "✅ Заблокированных пользователей нет",
                show_alert=True
            )
            return

        # Формируем текст со списком заблокированных пользователей
        text = f"🚫 <b>Заблокированные пользователи</b> ({len(blocked_users)})\n\n"

        for user in blocked_users:
            username = f"@{user.get('username')}" if user.get('username') else "нет username"
            reason = user.get('block_reason', 'не указана')

            text += (
                f"🚫 <b>{user.get('first_name', 'Без имени')}</b> ({username})\n"
                f"   ID: <code>{user.get('telegram_id')}</code>\n"
                f"   Причина: {reason}\n\n"
            )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_users_menu()  # Кнопка "Назад к управлению пользователями"
        )
        await callback.answer()
        logger.info(f"✅ Список заблокированных пользователей отправлен администратору {callback.from_user.id}")

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в handle_users_blocked: {e}",
            exc_info=True
        )
        await callback.answer("❌ Ошибка отображения списка", show_alert=True)


@router.callback_query(F.data == "users_active")
async def handle_users_active(callback: CallbackQuery):
    """
    Обработчик кнопки "Активные сегодня".

    ИСПРАВЛЕНИЕ: Добавлен полностью отсутствующий обработчик.
    Показывает пользователей, которые были активны сегодня.
    """
    try:
        logger.info(f"✅ Пользователь {callback.from_user.id} запросил список активных сегодня пользователей")

        try:
            # Получаем всех пользователей
            all_users = await get_all_users(limit=1000)
            logger.info(f"📊 Получено {len(all_users) if all_users else 0} пользователей для фильтрации")

            # ИСПРАВЛЕНИЕ v2: Фильтруем пользователей, активных сегодня
            # Теперь работаем с datetime объектами напрямую
            from datetime import datetime, timedelta
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

            logger.info(f"🕐 Начало сегодняшнего дня (UTC): {today_start}")

            active_today = []
            for user in all_users:
                # ИСПРАВЛЕНИЕ: Теперь last_activity - это datetime объект, а не строка
                last_activity = user.get('last_activity')

                # Логируем каждого пользователя для отладки
                logger.debug(
                    f"👤 Проверяем пользователя {user.get('telegram_id')}: "
                    f"last_activity={last_activity}, type={type(last_activity)}"
                )

                if last_activity and isinstance(last_activity, datetime):
                    # Сравниваем datetime объекты напрямую
                    if last_activity >= today_start:
                        active_today.append(user)
                        logger.info(
                            f"✅ Найден активный пользователь: {user.get('first_name')} "
                            f"(ID: {user.get('telegram_id')}), активность: {last_activity}"
                        )

            logger.info(f"📊 Найдено {len(active_today)} пользователей, активных сегодня")

        except Exception as db_error:
            logger.error(
                f"❌ Ошибка при получении активных пользователей из БД: {db_error}",
                exc_info=True
            )
            await callback.answer(
                "❌ Ошибка загрузки данных из базы",
                show_alert=True
            )
            return

        if not active_today:
            logger.info("ℹ️ Активных сегодня пользователей не найдено")
            await callback.answer(
                "ℹ️ Сегодня никто не был активен",
                show_alert=True
            )
            return

        # Формируем текст со списком активных пользователей
        text = f"✅ <b>Активные сегодня</b> ({len(active_today)})\n\n"

        for user in active_today[:50]:  # Показываем максимум 50 пользователей
            username = f"@{user.get('username')}" if user.get('username') else "нет username"
            # ИСПРАВЛЕНИЕ: Используем форматированную строку вместо datetime объекта
            last_activity = user.get('last_activity_str', 'неизвестно')

            text += (
                f"✅ <b>{user.get('first_name', 'Без имени')}</b> ({username})\n"
                f"   ID: <code>{user.get('telegram_id')}</code>\n"
                f"   Последняя активность: {last_activity}\n\n"
            )

        if len(active_today) > 50:
            text += f"\n... и ещё {len(active_today) - 50} пользователей"

        await callback.message.edit_text(
            text=text,
            reply_markup=get_users_menu()  # Кнопка "Назад к управлению пользователями"
        )
        await callback.answer()
        logger.info(f"✅ Список активных пользователей ({len(active_today)}) отправлен администратору {callback.from_user.id}")

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в handle_users_active: {e}",
            exc_info=True
        )
        await callback.answer("❌ Ошибка отображения списка", show_alert=True)


@router.callback_query(F.data == "users_new")
async def handle_users_new(callback: CallbackQuery):
    """
    Обработчик кнопки "Новые пользователи".

    ИСПРАВЛЕНИЕ: Добавлен полностью отсутствующий обработчик.
    Показывает пользователей, зарегистрированных за последние 7 дней.
    """
    try:
        logger.info(f"🆕 Пользователь {callback.from_user.id} запросил список новых пользователей")

        try:
            # Получаем всех пользователей
            all_users = await get_all_users(limit=1000)
            logger.info(f"📊 Получено {len(all_users) if all_users else 0} пользователей для фильтрации")

            # ИСПРАВЛЕНИЕ v2: Фильтруем новых пользователей (зарегистрированных за последние 7 дней)
            # Теперь работаем с datetime объектами напрямую
            from datetime import datetime, timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)

            logger.info(f"🕐 7 дней назад (UTC): {week_ago}")

            new_users = []
            for user in all_users:
                # ИСПРАВЛЕНИЕ: Теперь registration_date - это datetime объект, а не строка
                registration_date = user.get('registration_date')

                # Логируем каждого пользователя для отладки
                logger.debug(
                    f"👤 Проверяем пользователя {user.get('telegram_id')}: "
                    f"registration_date={registration_date}, type={type(registration_date)}"
                )

                if registration_date and isinstance(registration_date, datetime):
                    # Сравниваем datetime объекты напрямую
                    if registration_date >= week_ago:
                        new_users.append(user)
                        logger.info(
                            f"🆕 Найден новый пользователь: {user.get('first_name')} "
                            f"(ID: {user.get('telegram_id')}), регистрация: {registration_date}"
                        )

            logger.info(f"📊 Найдено {len(new_users)} новых пользователей за последние 7 дней")

        except Exception as db_error:
            logger.error(
                f"❌ Ошибка при получении новых пользователей из БД: {db_error}",
                exc_info=True
            )
            await callback.answer(
                "❌ Ошибка загрузки данных из базы",
                show_alert=True
            )
            return

        if not new_users:
            logger.info("ℹ️ Новых пользователей за последние 7 дней не найдено")
            await callback.answer(
                "ℹ️ За последние 7 дней новых пользователей нет",
                show_alert=True
            )
            return

        # Формируем текст со списком новых пользователей
        text = f"🆕 <b>Новые пользователи</b> (за последние 7 дней: {len(new_users)})\n\n"

        for user in new_users[:50]:  # Показываем максимум 50 пользователей
            username = f"@{user.get('username')}" if user.get('username') else "нет username"
            # ИСПРАВЛЕНИЕ: Используем форматированную строку вместо datetime объекта
            registration_date = user.get('registration_date_str', 'неизвестно')

            text += (
                f"🆕 <b>{user.get('first_name', 'Без имени')}</b> ({username})\n"
                f"   ID: <code>{user.get('telegram_id')}</code>\n"
                f"   Регистрация: {registration_date}\n\n"
            )

        if len(new_users) > 50:
            text += f"\n... и ещё {len(new_users) - 50} пользователей"

        await callback.message.edit_text(
            text=text,
            reply_markup=get_users_menu()  # Кнопка "Назад к управлению пользователями"
        )
        await callback.answer()
        logger.info(f"✅ Список новых пользователей ({len(new_users)}) отправлен администратору {callback.from_user.id}")

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в handle_users_new: {e}",
            exc_info=True
        )
        await callback.answer("❌ Ошибка отображения списка", show_alert=True)


@router.message(StateFilter(AdminStates.waiting_user_search))
async def process_user_search(message: Message, state: FSMContext):
    """
    Обработчик ввода текста для поиска пользователя.

    ИСПРАВЛЕНИЕ: Добавлен обработчик для обработки ввода при поиске пользователя.
    Ищет пользователя по Telegram ID, username или имени.
    """
    try:
        # HIGH-003 FIX: Sanitize search query to prevent injection attacks
        search_query = sanitize_search_query(message.text.strip())
        logger.info(f"🔍 Администратор {message.from_user.id} выполняет поиск: '{search_query}'")

        # Возвращаем состояние в меню пользователей
        await state.set_state(AdminStates.users_menu)

        user_found = None

        # Пытаемся найти по Telegram ID (если это число)
        if search_query.isdigit():
            try:
                telegram_id = int(search_query)
                user_found = await get_user_by_telegram_id(telegram_id)
                logger.info(f"🔍 Поиск по Telegram ID {telegram_id}: {'найден' if user_found else 'не найден'}")
            except Exception as search_error:
                logger.error(f"❌ Ошибка при поиске по ID: {search_error}")

        # Если не нашли по ID или это не число - ищем по username/имени
        if not user_found:
            try:
                all_users = await get_all_users(limit=1000)

                # Убираем @ из username если есть
                search_clean = search_query.lstrip('@').lower()

                for user in all_users:
                    # Поиск по username
                    if user.get('username') and user.get('username').lower() == search_clean:
                        user_found = user
                        logger.info(f"🔍 Найден пользователь по username: @{user.get('username')}")
                        break

                    # Поиск по имени
                    if user.get('first_name') and search_query.lower() in user.get('first_name', '').lower():
                        user_found = user
                        logger.info(f"🔍 Найден пользователь по имени: {user.get('first_name')}")
                        break

            except Exception as search_error:
                logger.error(f"❌ Ошибка при поиске пользователя: {search_error}", exc_info=True)
                await message.answer(
                    "❌ Ошибка поиска. Попробуйте ещё раз.",
                    reply_markup=get_users_menu()
                )
                return

        # Если пользователь не найден
        if not user_found:
            logger.info(f"ℹ️ Пользователь не найден по запросу: '{search_query}'")
            await message.answer(
                f"❌ Пользователь '<code>{search_query}</code>' не найден.\n\n"
                "Попробуйте другой запрос или вернитесь в меню.",
                reply_markup=get_users_menu()
            )
            return

        # Формируем информацию о найденном пользователе
        status_emoji = "🚫" if user_found.get('is_blocked') else "✅"
        username = f"@{user_found.get('username')}" if user_found.get('username') else "нет username"

        # ИСПРАВЛЕНИЕ: Используем форматированные строки для дат
        text = (
            f"🔍 <b>Найден пользователь</b>\n\n"
            f"{status_emoji} <b>{user_found.get('first_name', 'Без имени')} {user_found.get('last_name', '')}</b>\n"
            f"Username: {username}\n"
            f"Telegram ID: <code>{user_found.get('telegram_id')}</code>\n"
            f"Регистрация: {user_found.get('registration_date_str', 'неизвестно')}\n"
            f"Последняя активность: {user_found.get('last_activity_str', 'неизвестно')}\n"
            f"Статус: {'Заблокирован' if user_found.get('is_blocked') else 'Активен'}\n"
        )

        if user_found.get('is_blocked') and user_found.get('block_reason'):
            text += f"Причина блокировки: {user_found.get('block_reason')}\n"

        await message.answer(
            text=text,
            reply_markup=get_users_menu()
        )
        logger.info(f"✅ Результаты поиска отправлены администратору {message.from_user.id}")

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в process_user_search: {e}",
            exc_info=True
        )
        await message.answer(
            "❌ Ошибка выполнения поиска",
            reply_markup=get_users_menu()
        )
        # Возвращаем состояние в меню
        await state.set_state(AdminStates.users_menu)


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
    """
    Показывает меню управления контентом.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #4: Добавлено логирование.
    """
    try:
        logger.info(f"✏️ Пользователь {callback.from_user.id} открывает меню редактирования контента")

        await state.set_state(AdminStates.content_management)

        text = (
            "✏️ <b>Редактирование контента</b>\n\n"
            "Выберите раздел для редактирования:"
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_content_menu()
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"❌ Ошибка показа меню контента: {e}", exc_info=True)
        await callback.answer("Ошибка", show_alert=True)


@router.callback_query(F.data.startswith("content_"))
async def handle_content_section(callback: CallbackQuery, state: FSMContext):
    """
    MVP FEATURE: Полноценная реализация редактирования контента.

    ИСПРАВЛЕНИЕ: Изменен статус с "В разработке" на рабочий.

    Позволяет администратору:
    - Просматривать структуру JSON-файлов
    - Редактировать отдельные разделы
    - Сохранять изменения
    """
    section = callback.data.replace("content_", "")

    logger.info(f"📝 Пользователь {callback.from_user.id} открывает редактор контента '{section}'")

    section_names = {
        "general": "Общая информация",
        "sales": "Отдел продаж",
        "sport": "Спортивный отдел",
        "upload_video": "Загрузка видео",
        "upload_doc": "Загрузка документов"
    }

    section_name = section_names.get(section, section)

    # MVP: Обработка загрузки файлов - оставляем как "в разработке"
    if section in ["upload_video", "upload_doc"]:
        text = (
            f"✏️ <b>{section_name}</b>\n\n"
            "⚠️ <b>Функция в разработке</b>\n\n"
            "Загрузка медиафайлов через бота будет доступна в следующей версии.\n\n"
            "Пока используйте прямую загрузку в папку content/media/"
        )
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=get_back_to_admin()
            )
            await callback.answer()
            logger.info(f"✅ Показано сообщение о разработке для '{section}'")
        except Exception as e:
            logger.error(f"❌ Ошибка показа сообщения: {e}", exc_info=True)
            await callback.answer("Ошибка", show_alert=True)
        return

    # MVP: Редактирование JSON-файлов
    file_mapping = {
        "general": "general_info.json",
        "sales": "sales.json",
        "sport": "sport.json"
    }

    if section not in file_mapping:
        await callback.answer("Неизвестный раздел", show_alert=True)
        return

    file_name = file_mapping[section]
    file_path = Path("content/texts") / file_name

    try:
        # Загружаем JSON файл
        with open(file_path, 'r', encoding='utf-8') as f:
            content_data = json.load(f)

        logger.info(f"✅ Загружен файл {file_name}, найдено {len(content_data)} разделов")

        # Создаем клавиатуру с ключами
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard_buttons = []
        for key in content_data.keys():
            # Создаем читаемое название для ключа
            display_name = key.replace("_", " ").title()
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=f"📝 {display_name}",
                    callback_data=f"edit_{section}_{key}"
                )
            ])

        # Добавляем кнопку "Назад"
        keyboard_buttons.append([
            InlineKeyboardButton(
                text="◀️ Назад к выбору раздела",
                callback_data="admin_content"
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        text = (
            f"✏️ <b>Редактирование: {section_name}</b>\n\n"
            f"📄 Файл: <code>{file_name}</code>\n"
            f"📊 Разделов: {len(content_data)}\n\n"
            "Выберите раздел для редактирования:"
        )

        # Сохраняем в state текущий раздел
        await state.update_data(
            current_section=section,
            current_file=file_name,
            content_data=content_data
        )
        await state.set_state(AdminStates.content_select_section)

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard
        )
        await callback.answer()
        logger.info(f"✅ Показано меню выбора ключей для '{section}'")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке content_{section}: {e}", exc_info=True)
        await callback.answer(
            "Произошла ошибка при загрузке файла",
            show_alert=True
        )


@router.callback_query(F.data.startswith("edit_"))
async def handle_edit_key(callback: CallbackQuery, state: FSMContext):
    """
    MVP FEATURE: Показывает текущее содержимое выбранного ключа и просит новое значение.

    Обрабатывает callback вида: edit_{section}_{key}
    """
    try:
        # Парсим callback_data: edit_general_main_menu
        parts = callback.data.split("_", 2)  # ["edit", "general", "main_menu"]
        if len(parts) < 3:
            await callback.answer("Ошибка формата", show_alert=True)
            return

        section = parts[1]
        key = parts[2]

        logger.info(f"✏️ Пользователь {callback.from_user.id} редактирует ключ '{key}' в разделе '{section}'")

        # Получаем данные из state
        user_data = await state.get_data()
        content_data = user_data.get("content_data", {})

        if key not in content_data:
            await callback.answer(f"Ключ '{key}' не найден", show_alert=True)
            return

        current_value = content_data[key]

        # Форматируем текущее значение для отображения
        if isinstance(current_value, dict):
            current_value_str = json.dumps(current_value, ensure_ascii=False, indent=2)
            value_type = "JSON объект"
        elif isinstance(current_value, list):
            current_value_str = json.dumps(current_value, ensure_ascii=False, indent=2)
            value_type = "JSON массив"
        else:
            current_value_str = str(current_value)
            value_type = "Текст"

        # Ограничиваем длину для отображения в сообщении
        if len(current_value_str) > 800:
            display_value = current_value_str[:800] + "\n...\n(показано первые 800 символов)"
        else:
            display_value = current_value_str

        display_name = key.replace("_", " ").title()

        text = (
            f"✏️ <b>Редактирование ключа</b>\n\n"
            f"📝 Ключ: <code>{key}</code>\n"
            f"📊 Тип: {value_type}\n\n"
            f"<b>Текущее значение:</b>\n"
            f"<pre>{display_value}</pre>\n\n"
            f"📤 <b>Отправьте новое значение:</b>\n"
            f"• Для простого текста - просто напишите текст\n"
            f"• Для JSON - отправьте валидный JSON\n\n"
            f"⚠️ Будьте внимательны! Изменения сохранятся в файл."
        )

        # Клавиатура с кнопкой отмены
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="❌ Отменить редактирование",
                callback_data=f"content_{section}"
            )]
        ])

        # Сохраняем в state информацию о редактируемом ключе
        await state.update_data(
            editing_key=key,
            editing_section=section
        )
        await state.set_state(AdminStates.content_editing)

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard
        )
        await callback.answer()
        logger.info(f"✅ Показано текущее значение ключа '{key}', ожидаем новое значение")

    except Exception as e:
        logger.error(f"❌ Ошибка при показе редактора ключа: {e}", exc_info=True)
        await callback.answer("Ошибка", show_alert=True)


@router.message(StateFilter(AdminStates.content_editing))
async def handle_new_content(message: Message, state: FSMContext):
    """
    MVP FEATURE: Принимает новое содержимое и сохраняет в JSON файл.

    Обрабатывает текстовое сообщение с новым значением для ключа.
    """
    try:
        logger.info(f"📥 Получено новое содержимое от пользователя {message.from_user.id}")

        # Получаем данные из state
        user_data = await state.get_data()
        key = user_data.get("editing_key")
        section = user_data.get("editing_section")
        file_name = user_data.get("current_file")
        content_data = user_data.get("content_data", {})

        if not all([key, section, file_name]):
            await message.answer("❌ Ошибка: данные сессии потеряны. Начните заново.")
            await state.clear()
            return

        new_value_text = message.text.strip()

        # Пытаемся распарсить как JSON
        try:
            new_value = json.loads(new_value_text)
            logger.info(f"✅ Новое значение успешно распарсено как JSON")
        except json.JSONDecodeError:
            # Если не JSON, берем как простую строку
            new_value = new_value_text
            logger.info(f"ℹ️ Новое значение сохранено как обычный текст")

        # Обновляем значение в словаре
        old_value = content_data.get(key)
        content_data[key] = new_value

        # Сохраняем в файл
        file_path = Path("content/texts") / file_name

        # Создаем бэкап
        backup_path = Path("content/texts") / f"{file_name}.backup"
        if file_path.exists():
            shutil.copy2(file_path, backup_path)
            logger.info(f"✅ Создан бэкап: {backup_path}")

        # Сохраняем обновленный JSON
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Файл {file_name} успешно обновлен. Ключ '{key}' изменен")

        # Формируем сообщение об успехе
        if isinstance(new_value, (dict, list)):
            new_value_preview = json.dumps(new_value, ensure_ascii=False, indent=2)[:200]
        else:
            new_value_preview = str(new_value)[:200]

        text = (
            f"✅ <b>Изменения сохранены!</b>\n\n"
            f"📄 Файл: <code>{file_name}</code>\n"
            f"📝 Ключ: <code>{key}</code>\n\n"
            f"<b>Новое значение:</b>\n"
            f"<pre>{new_value_preview}</pre>\n\n"
            f"💾 Создан бэкап: <code>{backup_path.name}</code>\n\n"
            f"Изменения вступят в силу при следующем запросе этого раздела."
        )

        # Клавиатура для дальнейших действий
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📝 Редактировать другой ключ",
                callback_data=f"content_{section}"
            )],
            [InlineKeyboardButton(
                text="◀️ К выбору раздела",
                callback_data="admin_content"
            )],
            [InlineKeyboardButton(
                text="🏠 В главное меню админки",
                callback_data="admin_panel"
            )]
        ])

        await message.answer(
            text=text,
            reply_markup=keyboard
        )

        # Очищаем state редактирования
        await state.set_state(AdminStates.authorized)
        logger.info(f"✅ Редактирование завершено успешно")

    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении нового содержимого: {e}", exc_info=True)
        await message.answer(
            f"❌ <b>Ошибка при сохранении:</b>\n\n"
            f"<code>{str(e)}</code>\n\n"
            f"Изменения НЕ сохранены. Проверьте формат данных и попробуйте снова."
        )


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


@router.callback_query(F.data.startswith("broadcast_send_"))
async def send_broadcast(callback: CallbackQuery, state: FSMContext):
    """
    Отправляет рассылку.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Обработчик перемещен ВЫШЕ process_broadcast_target.
    Ранее из-за неправильного порядка обработчиков callback "broadcast_send_all"
    сначала обрабатывался в process_broadcast_target, где target = "send_all"
    не проходил проверку и выдавал ошибку "Неизвестная аудитория".
    """
    try:
        logger.info(f"📤 Пользователь {callback.from_user.id} подтвердил отправку рассылки")

        data = await state.get_data()
        broadcast_text = data.get("broadcast_text")
        target = data.get("broadcast_target")

        logger.info(f"📊 Рассылка для аудитории: {target}, текст: {broadcast_text[:50] if broadcast_text else 'None'}...")

        await state.set_state(AdminStates.broadcast_sending)

        # Получаем список получателей
        if target == "all":
            users = await get_all_users()
            logger.info(f"📋 Получено {len(users) if users else 0} пользователей для рассылки 'всем'")
        elif target == "active":
            users = await get_all_users()  # TODO: фильтровать активных
            logger.info(f"📋 Получено {len(users) if users else 0} активных пользователей")
        else:
            users = []
            logger.warning(f"⚠️ Неизвестная аудитория: {target}")

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

    except Exception as e:
        logger.error(f"❌ Критическая ошибка при отправке рассылки: {e}", exc_info=True)
        await callback.answer("Ошибка отправки рассылки", show_alert=True)


@router.callback_query(F.data.startswith("broadcast_"))
async def process_broadcast_target(callback: CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор целевой аудитории.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлена проверка на "send_" в начале target.
    Ранее callback_data "broadcast_send_all" также попадал в этот обработчик,
    но после удаления "broadcast_" получалось target="send_all", которое
    не проходило ни одну проверку и выдавало "Неизвестная аудитория".

    Теперь такие callback игнорируются, т.к. они обрабатываются в send_broadcast выше.
    """
    target = callback.data.replace("broadcast_", "")

    # ИСПРАВЛЕНИЕ: Игнорируем callback'и для отправки (они обрабатываются выше)
    if target.startswith("send_"):
        logger.debug(f"Игнорируем broadcast_send_ callback в process_broadcast_target")
        return

    logger.info(f"📢 Пользователь {callback.from_user.id} выбрал аудиторию рассылки: {target}")

    if target == "history":
        await callback.answer("История рассылок - в разработке", show_alert=True)
        return

    # Подсчитываем количество получателей
    try:
        if target == "all":
            count = await get_active_users_count()
            target_text = "всем пользователям"
            logger.info(f"✅ Выбрана аудитория 'все пользователи': {count} чел.")
        elif target == "sales":
            count = 0  # TODO: Реализовать подсчет по отделам
            target_text = "отделу продаж"
            logger.warning(f"⚠️ Аудитория 'отдел продаж' не реализована")
        elif target == "sport":
            count = 0
            target_text = "спортивному отделу"
            logger.warning(f"⚠️ Аудитория 'спортивный отдел' не реализована")
        elif target == "active":
            count = await get_active_users_count()
            target_text = "активным пользователям"
            logger.info(f"✅ Выбрана аудитория 'активные': {count} чел.")
        else:
            logger.error(f"❌ Неизвестная аудитория: {target}")
            await callback.answer("Неизвестная аудитория", show_alert=True)
            return

    except Exception as e:
        logger.error(f"❌ Ошибка при подсчете аудитории '{target}': {e}", exc_info=True)
        await callback.answer("Ошибка получения данных об аудитории", show_alert=True)
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
    # HIGH-003 FIX: Sanitize broadcast message to prevent HTML injection
    broadcast_text = sanitize_broadcast_message(message.text, max_length=4096)
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


# ИСПРАВЛЕНИЕ: Старый обработчик send_broadcast удален, т.к. новый добавлен выше (строка 784)
# с улучшенным логированием и обработкой ошибок


# ========== ЛОГИ ==========

@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery):
    """
    Показывает последние 50 действий пользователей.

    MVP FEATURE: Полноценная реализация просмотра логов активности.
    ИСПРАВЛЕНИЕ: Изменен статус с "В разработке" на рабочий.
    """
    try:
        logger.info(f"📋 Администратор {callback.from_user.id} запросил просмотр логов активности")

        # MVP: Получаем последние 50 действий
        try:
            recent_logs = await get_recent_activity(limit=50)
            logger.info(f"✅ Получено {len(recent_logs)} записей логов")
        except Exception as logs_error:
            logger.error(
                f"❌ Ошибка при получении логов: {logs_error}",
                exc_info=True
            )
            await callback.answer(
                "❌ Ошибка загрузки логов активности",
                show_alert=True
            )
            return

        # MVP: Формируем красивый вывод
        if recent_logs:
            text = f"📋 <b>Последние {len(recent_logs)} действий</b>\n\n"

            for log in recent_logs[:20]:  # Показываем только первые 20 в сообщении
                # Форматируем вывод: кто, что, когда
                username_display = f"@{log['username']}" if log['username'] != "без username" else log['first_name']
                action_text = log['action'].replace("_", " ").title()

                text += (
                    f"👤 {username_display} (ID: {log['telegram_id']})\n"
                    f"   📌 {action_text}"
                )

                # Добавляем раздел если есть
                if log['section'] != "-":
                    text += f" → {log['section']}"

                text += f"\n   🕐 {log['timestamp_str']}\n\n"

            # Если логов больше 20, добавляем информацию
            if len(recent_logs) > 20:
                text += f"... и ещё {len(recent_logs) - 20} записей\n\n"

            text += (
                "ℹ️ Для выгрузки полного лога за 30 дней используйте кнопку <b>Экспорт логов</b>.\n\n"
                "📊 Всего показано записей: 20 из 50"
            )
        else:
            # MVP: Информативное сообщение
            text = (
                "📋 <b>Логи активности</b>\n\n"
                "В журнале пока только эти события.\n\n"
                "ℹ️ Логирование активности происходит автоматически при действиях пользователей."
            )

        # Добавляем кнопку для экспорта
        from keyboards.admin_kb import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="📥 Экспорт логов в файл",
                callback_data="export_logs"
            )],
            [InlineKeyboardButton(
                text="◀️ Назад к админке",
                callback_data="return_to_admin"
            )]
        ])

        await callback.message.edit_text(
            text=text,
            reply_markup=keyboard
        )
        await callback.answer()

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в show_logs: {e}",
            exc_info=True
        )
        await callback.answer("❌ Ошибка отображения логов", show_alert=True)


@router.callback_query(F.data == "export_logs")
async def export_logs_to_file(callback: CallbackQuery):
    """
    Выгружает логи активности в текстовый файл.

    MVP FEATURE: Экспорт логов за последние 30 дней в .txt файл.
    """
    try:
        logger.info(f"📥 Администратор {callback.from_user.id} запросил экспорт логов")

        await callback.answer("⏳ Генерация файла...", show_alert=False)

        # Получаем все логи за последние 30 дней
        try:
            all_logs = await get_all_activity_for_export(days=30)
            logger.info(f"✅ Получено {len(all_logs)} записей для экспорта")
        except Exception as export_error:
            logger.error(
                f"❌ Ошибка при получении логов для экспорта: {export_error}",
                exc_info=True
            )
            await callback.answer(
                "❌ Ошибка получения данных для экспорта",
                show_alert=True
            )
            return

        if not all_logs:
            await callback.answer(
                "ℹ️ Нет данных для экспорта",
                show_alert=True
            )
            return

        # Генерируем текстовый файл
        # Создаем временный файл
        # TIMEZONE: Используем московское время для имени файла и метки времени
        timestamp = get_msk_now().strftime("%Y%m%d_%H%M%S")
        filename = f"activity_logs_{timestamp}.txt"

        # MVP: Формируем содержимое файла
        content_lines = [
            "=" * 80,
            f"ЛОГИ АКТИВНОСТИ ПОЛЬЗОВАТЕЛЕЙ",
            f"Период: последние 30 дней",
            # TIMEZONE: Время генерации файла в МСК
            f"Сгенерировано: {get_msk_now().strftime('%d.%m.%Y %H:%M:%S')} (МСК)",
            f"Всего записей: {len(all_logs)}",
            "=" * 80,
            ""
        ]

        for i, log in enumerate(all_logs, 1):
            username = f"@{log['username']}" if log['username'] else log['first_name']
            full_name = f"{log['first_name']} {log['last_name']}".strip()

            content_lines.extend([
                f"[{i}] {log['timestamp']}",
                f"    Пользователь: {full_name} ({username})",
                f"    Telegram ID: {log['telegram_id']}",
                f"    Действие: {log['action']}",
                f"    Раздел: {log['section'] or '-'}",
                f"    Подраздел: {log['subsection'] or '-'}",
                f"    Callback: {log['callback_data'] or '-'}",
                "-" * 80,
                ""
            ])

        content = "\n".join(content_lines)

        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', suffix='.txt', delete=False) as f:
            f.write(content)
            temp_path = f.name

        # Отправляем файл пользователю
        document = FSInputFile(temp_path, filename=filename)

        # TIMEZONE: Время генерации в caption в МСК
        await callback.message.answer_document(
            document=document,
            caption=(
                f"📥 <b>Логи активности</b>\n\n"
                f"📊 Всего записей: {len(all_logs)}\n"
                f"📅 Период: 30 дней\n"
                f"🕐 Сгенерировано: {get_msk_now().strftime('%d.%m.%Y %H:%M:%S')} (МСК)"
            )
        )

        # Удаляем временный файл
        Path(temp_path).unlink(missing_ok=True)

        await callback.answer("✅ Файл отправлен!")
        logger.info(f"✅ Логи успешно экспортированы для администратора {callback.from_user.id}: {len(all_logs)} записей")

    except Exception as e:
        logger.error(
            f"❌ Критическая ошибка в export_logs_to_file: {e}",
            exc_info=True
        )
        await callback.answer("❌ Ошибка экспорта логов", show_alert=True)

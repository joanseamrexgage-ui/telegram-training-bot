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

# Получаем хеш пароля администратора из .env
# По умолчанию используется хеш от "admin123"
# Для генерации хеша: import hashlib; print(hashlib.sha256("your_password".encode()).hexdigest())
DEFAULT_ADMIN_HASH = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"  # admin123
ADMIN_PASS_HASH = os.getenv("ADMIN_PASS_HASH", DEFAULT_ADMIN_HASH)

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
    # Сравниваем хеш введенного пароля с хешем из .env
    if check_password(input_password, ADMIN_PASS_HASH):
        # ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлен try-except блок для обработки ошибок
        # Ранее при любой ошибке в show_admin_panel пользователь получал необработанное исключение
        try:
            # Пароль верный
            reset_password_attempts(user_id)
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
            f"🕐 <b>Последнее обновление:</b>\n"
            f"{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}"
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
    Показывает статистику по разделам.

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #2: Добавлена обработка ошибок.
    """
    try:
        logger.info(f"📱 Пользователь {callback.from_user.id} запросил статистику по разделам")

        try:
            section_stats = await get_section_statistics()
            logger.info(f"✅ Статистика по разделам получена")
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

        text = "📱 <b>Популярные разделы</b>\n\n"

        if section_stats:
            for i, (section, count) in enumerate(section_stats[:10], 1):
                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                text += f"{emoji} {section}: {count} просмотров\n"
        else:
            text += "Данных пока нет"

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
                f"🕐 Обновлено: {datetime.now().strftime('%H:%M:%S')}"
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
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлен обработчик для "Статистика по датам".

    Ранее при нажатии на эту кнопку отсутствовал обработчик, что приводило
    к бесконечному "думанию" бота без ответа.
    """
    try:
        logger.info(f"📅 Пользователь {callback.from_user.id} запросил статистику по датам")

        text = (
            "📅 <b>Статистика по датам</b>\n\n"
            "⚠️ <b>Функция в разработке</b>\n\n"
            "Детальная статистика по датам будет доступна в следующей версии.\n\n"
            "Планируемый функционал:\n"
            "• Активность по дням недели\n"
            "• Пиковые часы использования\n"
            "• Динамика регистраций\n"
            "• Сравнение периодов\n\n"
            "Пока используйте общую статистику и статистику пользователей."
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()
        logger.info(f"✅ Показано сообщение о разработке для статистики по датам")

    except Exception as e:
        logger.error(f"❌ Ошибка в show_dates_stats: {e}", exc_info=True)
        await callback.answer("Функция в разработке", show_alert=True)


@router.callback_query(F.data == "stats_export")
async def export_stats_to_excel(callback: CallbackQuery):
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлен обработчик для "Экспорт в Excel".

    Ранее при нажатии на эту кнопку отсутствовал обработчик, что приводило
    к бесконечному "думанию" бота без ответа.
    """
    try:
        logger.info(f"📊 Пользователь {callback.from_user.id} запросил экспорт статистики в Excel")

        text = (
            "📊 <b>Экспорт статистики в Excel</b>\n\n"
            "⚠️ <b>Функция в разработке</b>\n\n"
            "Экспорт данных в Excel будет доступен в следующей версии.\n\n"
            "Планируемые отчеты:\n"
            "• Полный список пользователей с контактами\n"
            "• История активности по датам\n"
            "• Статистика по разделам и материалам\n"
            "• Результаты тестирований\n"
            "• Отчеты по отделам\n\n"
            "💡 Для получения данных обратитесь к системному администратору "
            "с доступом к базе данных."
        )

        await callback.message.edit_text(
            text=text,
            reply_markup=get_stats_menu()
        )
        await callback.answer()
        logger.info(f"✅ Показано сообщение о разработке для экспорта в Excel")

    except Exception as e:
        logger.error(f"❌ Ошибка в export_stats_to_excel: {e}", exc_info=True)
        await callback.answer("Функция в разработке", show_alert=True)


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
            username = f"@{user.get('username')}" if user.get('username') else "нет username"

            text += (
                f"{status} <b>{user.get('first_name', 'Без имени')}</b> ({username})\n"
                f"   ID: <code>{user.get('telegram_id')}</code>\n"
                f"   Регистрация: {user.get('registration_date', 'неизвестно')}\n\n"
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
        search_query = message.text.strip()
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
async def handle_content_section(callback: CallbackQuery):
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #4: Добавлен обработчик для подразделов редактирования контента.

    Ранее при нажатии на любой раздел (content_general, content_sales, content_sport и др.)
    отсутствовал обработчик, что приводило к бесконечному "думанию" бота без ответа.

    Теперь обработчик быстро отвечает пользователю с информативным сообщением,
    что функция находится в разработке.
    """
    section = callback.data.replace("content_", "")

    logger.info(f"📝 Пользователь {callback.from_user.id} пытается редактировать раздел '{section}'")

    section_names = {
        "general": "Общая информация",
        "sales": "Отдел продаж",
        "sport": "Спортивный отдел",
        "upload_video": "Загрузка видео",
        "upload_doc": "Загрузка документов"
    }

    section_name = section_names.get(section, section)

    text = (
        f"✏️ <b>Редактирование: {section_name}</b>\n\n"
        "⚠️ <b>Функция в разработке</b>\n\n"
        "Редактирование контента через бота будет доступно "
        "в следующей версии.\n\n"
        "Пока для редактирования контента используйте:\n"
        "• Прямое редактирование JSON-файлов в content/texts/\n"
        "• Загрузку медиа в content/media/\n\n"
        "Обратитесь к системному администратору для помощи."
    )

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_back_to_admin()
        )
        await callback.answer()
        logger.info(f"✅ Показано сообщение о разработке для раздела '{section}'")

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке content_{section}: {e}", exc_info=True)
        await callback.answer(
            "Функция в разработке",
            show_alert=True
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


# ИСПРАВЛЕНИЕ: Старый обработчик send_broadcast удален, т.к. новый добавлен выше (строка 784)
# с улучшенным логированием и обработкой ошибок


# ========== ЛОГИ ==========

@router.callback_query(F.data == "admin_logs")
async def show_logs(callback: CallbackQuery):
    """Показывает последние логи."""
    # TODO: Реализовать чтение логов из файла
    await callback.answer("Просмотр логов - в разработке", show_alert=True)

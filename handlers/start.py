"""
Обработчики команды /start и главного меню
"""

from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from keyboards.inline import get_main_menu_keyboard, get_home_button
from states.menu_states import MenuStates
from database.models import User
from database.crud import UserCRUD
from utils.logger import logger, log_user_action
# HIGH-003 FIX: Input sanitization
from utils.sanitize import sanitize_user_input, sanitize_username

router = Router(name="start_router")

# Приветственное сообщение
WELCOME_TEXT = """
👋 <b>Добро пожаловать в корпоративный чат-бот для обучения сотрудников!</b>

🎯 <b>Цель бота:</b>
Помочь вам быстро освоиться на рабочем месте и получить всю необходимую информацию для эффективной работы.

📚 <b>Что вы найдете в боте:</b>
• Адреса и контакты всех парков
• Инструкции по работе с оборудованием
• Обучающие видео и материалы
• Правила и регламенты компании
• Ответы на часто задаваемые вопросы

🎓 <b>Как пользоваться ботом:</b>
1. Выберите нужный раздел в главном меню
2. Следуйте подсказкам и используйте кнопки навигации
3. В любой момент можете вернуться в главное меню

💡 <b>Подсказка:</b>
Используйте команды:
• /help - помощь по работе с ботом
• /menu - вернуться в главное меню
• /profile - ваш профиль

<b>Выберите интересующий раздел:</b>
"""

RETURN_TEXT = """
🏠 <b>Главное меню</b>

Выберите интересующий раздел:

🟢 <b>Общая информация</b> - адреса, контакты, правила
🔴 <b>Отдел продаж</b> - инструкции для менеджеров
🔵 <b>Спортивный отдел</b> - работа с оборудованием
🔐 <b>Администрация</b> - доступ для руководителей
"""


@router.message(CommandStart())
async def cmd_start(
    message: Message, 
    state: FSMContext,
    db_session: AsyncSession
):
    """Обработчик команды /start"""
    try:
        # Очищаем состояние
        await state.clear()
        
        # Получаем или создаем пользователя
        user = await UserCRUD.get_or_create_user(
            session=db_session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            language_code=message.from_user.language_code
        )
        
        # Устанавливаем состояние главного меню
        await state.set_state(MenuStates.main_menu)
        
        # Отправляем приветственное сообщение
        await message.answer(
            text=WELCOME_TEXT,
            reply_markup=get_main_menu_keyboard()
        )
        
        # Логируем действие
        log_user_action(
            user_id=message.from_user.id,
            username=message.from_user.username,
            action="start_command",
            details={"first_time": user.messages_count == 0}
        )
        
        # Увеличиваем счетчик команд
        await UserCRUD.increment_user_counter(
            session=db_session,
            telegram_id=message.from_user.id,
            counter_type="commands"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике /start: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при запуске бота. Попробуйте позже или обратитесь к администратору."
        )


@router.message(Command("menu"))
async def cmd_menu(
    message: Message,
    state: FSMContext,
    db_session: AsyncSession
):
    """Обработчик команды /menu - возврат в главное меню"""
    try:
        await state.set_state(MenuStates.main_menu)
        
        await message.answer(
            text=RETURN_TEXT,
            reply_markup=get_main_menu_keyboard()
        )
        
        # Логируем действие
        log_user_action(
            user_id=message.from_user.id,
            username=message.from_user.username,
            action="menu_command"
        )
        
        # Увеличиваем счетчик команд
        await UserCRUD.increment_user_counter(
            session=db_session,
            telegram_id=message.from_user.id,
            counter_type="commands"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике /menu: {e}", exc_info=True)


@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(
    callback: CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession
):
    """Возврат в главное меню через inline кнопку"""
    try:
        await state.set_state(MenuStates.main_menu)

        await callback.message.edit_text(
            text=RETURN_TEXT,
            reply_markup=get_main_menu_keyboard()
        )

        # Отвечаем на callback чтобы убрать "часики"
        await callback.answer()

        # Логируем действие
        log_user_action(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            action="back_to_main",
            details={"from_state": await state.get_state()}
        )

    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}", exc_info=True)
        await callback.answer(
            "Произошла ошибка. Используйте команду /menu",
            show_alert=True
        )


@router.callback_query(F.data == "main_menu")
async def handle_main_menu_button(
    callback: CallbackQuery,
    state: FSMContext,
    db_session: AsyncSession
):
    """
    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Обработчик кнопки "Главное меню"

    Ранее этот обработчик отсутствовал, из-за чего кнопка "Главное меню"
    во всех разделах (отдел продаж, спортивный отдел, общая информация)
    не работала - только мигала без перехода.

    Теперь обрабатывает callback_data="main_menu" из всех клавиатур:
    - keyboards/general_info_kb.py
    - keyboards/sales_kb.py
    - keyboards/sport_kb.py
    - keyboards/admin_kb.py
    """
    try:
        # Логируем попытку возврата в главное меню
        current_state = await state.get_state()
        logger.info(
            f"Пользователь {callback.from_user.id} (@{callback.from_user.username}) "
            f"возвращается в главное меню из состояния: {current_state}"
        )

        # Очищаем состояние и устанавливаем главное меню
        await state.set_state(MenuStates.main_menu)

        # Обновляем сообщение с главным меню
        await callback.message.edit_text(
            text=RETURN_TEXT,
            reply_markup=get_main_menu_keyboard()
        )

        # Отвечаем на callback чтобы убрать "часики"
        await callback.answer("🏠 Главное меню")

        # Логируем успешное действие
        log_user_action(
            user_id=callback.from_user.id,
            username=callback.from_user.username,
            action="main_menu_button",
            details={
                "from_state": current_state,
                "success": True
            }
        )

        logger.info(
            f"✅ Пользователь {callback.from_user.id} успешно вернулся в главное меню"
        )

    except Exception as e:
        # ИСПРАВЛЕНИЕ: Расширенное логирование ошибок с полным stack trace
        logger.error(
            f"❌ Ошибка при возврате в главное меню для пользователя {callback.from_user.id}: {e}",
            exc_info=True
        )
        await callback.answer(
            "Произошла ошибка. Попробуйте команду /menu",
            show_alert=True
        )


@router.message(Command("help"))
async def cmd_help(message: Message, db_session: AsyncSession):
    """Обработчик команды /help"""
    help_text = """
📖 <b>Помощь по работе с ботом</b>

<b>Основные команды:</b>
/start - перезапустить бота
/menu - главное меню
/help - эта справка
/profile - ваш профиль
/feedback - оставить отзыв

<b>Навигация:</b>
• Используйте кнопки под сообщениями для перемещения
• Кнопка "◀️ Назад" вернет на предыдущий уровень
• Кнопка "🏠 Главное меню" вернет в начало

<b>Разделы бота:</b>
🟢 <b>Общая информация</b>
Содержит базовую информацию для всех сотрудников

🔴 <b>Отдел продаж</b>
Специализированная информация для менеджеров по продажам

🔵 <b>Спортивный отдел</b>
Инструкции по работе с оборудованием и техника безопасности

🔐 <b>Администрация</b>
Закрытый раздел для руководителей (требуется пароль)

<b>Поддержка:</b>
Если у вас возникли вопросы или проблемы с ботом:
• Напишите администратору: @admin_username
• Позвоните: +7 (999) 000-00-00
• Используйте команду /feedback

<i>💡 Совет: сохраните важную информацию из бота в избранное Telegram для быстрого доступа</i>
"""
    
    try:
        await message.answer(
            text=help_text,
            reply_markup=get_home_button()
        )
        
        # Логируем действие
        log_user_action(
            user_id=message.from_user.id,
            username=message.from_user.username,
            action="help_command"
        )
        
        # Увеличиваем счетчик команд
        await UserCRUD.increment_user_counter(
            session=db_session,
            telegram_id=message.from_user.id,
            counter_type="commands"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике /help: {e}", exc_info=True)


@router.message(Command("profile"))
async def cmd_profile(
    message: Message,
    db_session: AsyncSession
):
    """Показать профиль пользователя"""
    try:
        # Получаем пользователя из БД
        user = await UserCRUD.get_user_by_telegram_id(
            session=db_session,
            telegram_id=message.from_user.id
        )
        
        if not user:
            await message.answer(
                "❌ Профиль не найден. Используйте /start для регистрации."
            )
            return
        
        # HIGH-003 FIX: Sanitize user data before display
        full_name = sanitize_user_input(user.full_name, max_length=100)
        username = sanitize_username(user.username) if user.username else 'не указан'
        department = sanitize_user_input(user.department or 'не указан', max_length=50)
        position = sanitize_user_input(user.position or 'не указана', max_length=100)
        park = sanitize_user_input(user.park_location or 'не указан', max_length=50)

        # Формируем текст профиля
        profile_text = f"""
👤 <b>Ваш профиль</b>

<b>Имя:</b> {full_name}
<b>Username:</b> @{username}
<b>ID:</b> <code>{user.telegram_id}</code>
<b>Отдел:</b> {department}
<b>Должность:</b> {position}
<b>Парк:</b> {park}

📊 <b>Статистика:</b>
<b>Дата регистрации:</b> {user.registration_date.strftime('%d.%m.%Y')}
<b>Последняя активность:</b> {user.last_activity.strftime('%d.%m.%Y %H:%M')}
<b>Сообщений отправлено:</b> {user.messages_count}
<b>Команд использовано:</b> {user.commands_count}

<i>Для изменения данных профиля обратитесь к администратору</i>
"""
        
        await message.answer(
            text=profile_text,
            reply_markup=get_home_button()
        )
        
        # Логируем действие
        log_user_action(
            user_id=message.from_user.id,
            username=message.from_user.username,
            action="profile_command"
        )
        
        # Увеличиваем счетчик команд
        await UserCRUD.increment_user_counter(
            session=db_session,
            telegram_id=message.from_user.id,
            counter_type="commands"
        )
        
    except Exception as e:
        logger.error(f"Ошибка в обработчике /profile: {e}", exc_info=True)
        await message.answer(
            "❌ Произошла ошибка при загрузке профиля."
        )


@router.message(Command("feedback"))
async def cmd_feedback(message: Message, state: FSMContext):
    """Начать процесс обратной связи"""
    # TODO: Реализовать в отдельном модуле feedback.py
    await message.answer(
        "📝 Функция обратной связи будет доступна в следующей версии.\n"
        "Пока вы можете написать администратору напрямую: @admin_username",
        reply_markup=get_home_button()
    )
    
    log_user_action(
        user_id=message.from_user.id,
        username=message.from_user.username,
        action="feedback_command"
    )


# Обработчик неизвестных команд
@router.message(Command("unknown"))
async def unknown_command(message: Message):
    """Обработчик неизвестных команд"""
    await message.answer(
        "❓ Неизвестная команда.\n"
        "Используйте /help для просмотра доступных команд.",
        reply_markup=get_home_button()
    )
    
    logger.info(f"Неизвестная команда от {message.from_user.id}: {message.text}")


# Обработчик обычных текстовых сообщений в состоянии главного меню
@router.message(MenuStates.main_menu)
async def echo_in_main_menu(message: Message):
    """Эхо-ответ в главном меню"""
    await message.answer(
        "🤖 Я понимаю только команды и кнопки.\n"
        "Пожалуйста, выберите раздел из меню ниже:",
        reply_markup=get_main_menu_keyboard()
    )

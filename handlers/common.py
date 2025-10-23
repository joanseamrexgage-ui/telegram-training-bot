"""
CRIT-003 FIX: Common handlers for universal callbacks (back, cancel, help)

Этот модуль содержит обработчики общих действий:
- Кнопка "Назад"
- Кнопка "Отмена"
- Помощь и информация
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command

from utils.logger import logger

# Создаем router для общих обработчиков
router = Router(name='common')


@router.callback_query(F.data == "back")
async def handle_back(callback: CallbackQuery):
    """Обработчик кнопки 'Назад'"""
    await callback.answer("⬅️ Возврат назад")
    # По умолчанию просто подтверждаем нажатие
    # Конкретные обработчики должны обрабатывать "back" в своих модулях


@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопки 'Отмена'"""
    # Очищаем состояние FSM
    await state.clear()

    await callback.message.edit_text(
        "❌ <b>Действие отменено</b>\n\n"
        "Используйте /start для возврата в главное меню"
    )
    await callback.answer("Отменено")
    logger.info(f"Пользователь {callback.from_user.id} отменил действие")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help"""
    help_text = (
        "ℹ️ <b>Справка по боту</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n\n"
        "<b>Разделы:</b>\n"
        "• 📚 Общая информация - базовые сведения\n"
        "• 💼 Отдел продаж - информация для менеджеров\n"
        "• ⚽ Спортивный отдел - для инструкторов\n"
        "• ⚙️ Админ-панель - управление ботом\n\n"
        "<b>Навигация:</b>\n"
        "Используйте кнопки под сообщениями для навигации по разделам.\n\n"
        "По вопросам обращайтесь к администратору."
    )

    await message.answer(help_text)
    logger.info(f"Пользователь {message.from_user.id} запросил помощь")


@router.callback_query(F.data == "help")
async def callback_help(callback: CallbackQuery):
    """Обработчик callback кнопки 'Помощь'"""
    help_text = (
        "ℹ️ <b>Справка по боту</b>\n\n"
        "<b>Доступные команды:</b>\n"
        "/start - Главное меню\n"
        "/help - Эта справка\n\n"
        "<b>Разделы:</b>\n"
        "• 📚 Общая информация - базовые сведения\n"
        "• 💼 Отдел продаж - информация для менеджеров\n"
        "• ⚽ Спортивный отдел - для инструкторов\n"
        "• ⚙️ Админ-панель - управление ботом\n\n"
        "<b>Навигация:</b>\n"
        "Используйте кнопки под сообщениями для навигации по разделам.\n\n"
        "По вопросам обращайтесь к администратору."
    )

    await callback.message.edit_text(help_text)
    await callback.answer()
    logger.info(f"Пользователь {callback.from_user.id} запросил помощь")

"""
CRUD операции для работы с базой данных
"""

from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    User, UserActivity, Content, TestQuestion,
    TestResult, TestAnswer, AdminLog, BroadcastMessage,
    Department, UserRole
)
# ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ #1: Добавлен импорт get_db_session
# Ранее функция get_db_session использовалась в wrapper-функциях (строки 650, 669, 686, 693, 700, 715...),
# но не была импортирована, что вызывало ошибку:
# NameError: name 'get_db_session' is not defined
# Это приводило к сбою всех обработчиков статистики и управления пользователями.
from database.database import get_db_session
from utils.logger import logger, log_database_operation
from utils.timezone import format_msk_datetime, utc_to_msk
import json


class UserCRUD:
    """CRUD операции для работы с пользователями"""
    
    @staticmethod
    async def get_or_create_user(
        session: AsyncSession,
        telegram_id: int,
        **kwargs
    ) -> User:
        """Получить или создать пользователя"""
        try:
            start_time = datetime.utcnow()
            
            # Пытаемся найти пользователя
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()
            
            if not user:
                # Создаем нового пользователя
                user = User(telegram_id=telegram_id, **kwargs)
                session.add(user)
                await session.commit()
                await session.refresh(user)
                
                duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                log_database_operation(
                    operation="INSERT",
                    model="User",
                    success=True,
                    duration_ms=duration_ms,
                    details={"telegram_id": telegram_id}
                )
                logger.info(f"Создан новый пользователь: {telegram_id}")
            else:
                # Обновляем данные существующего пользователя
                updated = False
                for key, value in kwargs.items():
                    if hasattr(user, key) and getattr(user, key) != value:
                        setattr(user, key, value)
                        updated = True

                # ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Обновляем время последней активности
                # Проблема: last_activity обновлялась, но коммитилась только если updated=True
                # Это приводило к тому, что при обычных действиях (клики) активность не сохранялась
                user.last_activity = datetime.utcnow()

                # ИСПРАВЛЕНИЕ: Всегда коммитим, чтобы сохранить обновленное время last_activity
                await session.commit()
                await session.refresh(user)
            
            return user
            
        except Exception as e:
            await session.rollback()
            log_database_operation(
                operation="INSERT/UPDATE",
                model="User",
                success=False,
                details={"error": str(e)}
            )
            raise
    
    @staticmethod
    async def get_user_by_telegram_id(
        session: AsyncSession,
        telegram_id: int
    ) -> Optional[User]:
        """Получить пользователя по Telegram ID"""
        try:
            stmt = select(User).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя {telegram_id}: {e}")
            return None
    
    @staticmethod
    async def get_user_by_id(
        session: AsyncSession,
        user_id: int
    ) -> Optional[User]:
        """Получить пользователя по ID"""
        try:
            stmt = select(User).where(User.id == user_id).options(
                selectinload(User.activities),
                selectinload(User.test_results)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Ошибка при получении пользователя по ID {user_id}: {e}")
            return None
    
    @staticmethod
    async def block_user(
        session: AsyncSession,
        telegram_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """Заблокировать пользователя"""
        try:
            stmt = (
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(
                    is_blocked=True,
                    block_reason=reason
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.warning(f"Пользователь {telegram_id} заблокирован. Причина: {reason}")
                return True
            return False
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при блокировке пользователя {telegram_id}: {e}")
            return False
    
    @staticmethod
    async def unblock_user(
        session: AsyncSession,
        telegram_id: int
    ) -> bool:
        """Разблокировать пользователя"""
        try:
            stmt = (
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(
                    is_blocked=False,
                    block_reason=None
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Пользователь {telegram_id} разблокирован")
                return True
            return False
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при разблокировке пользователя {telegram_id}: {e}")
            return False
    
    @staticmethod
    async def is_user_blocked(
        session: AsyncSession,
        telegram_id: int
    ) -> bool:
        """Проверить, заблокирован ли пользователь"""
        try:
            stmt = select(User.is_blocked).where(User.telegram_id == telegram_id)
            result = await session.execute(stmt)
            is_blocked = result.scalar_one_or_none()
            return is_blocked or False
        except Exception as e:
            logger.error(f"Ошибка при проверке блокировки пользователя {telegram_id}: {e}")
            return False
    
    @staticmethod
    async def get_all_users(
        session: AsyncSession,
        limit: int = 100,
        offset: int = 0,
        department: Optional[Department] = None,
        role: Optional[UserRole] = None,
        is_blocked: Optional[bool] = None
    ) -> List[User]:
        """Получить список пользователей с фильтрацией"""
        try:
            stmt = select(User)
            
            # Применяем фильтры
            if department:
                stmt = stmt.where(User.department == department)
            if role:
                stmt = stmt.where(User.role == role)
            if is_blocked is not None:
                stmt = stmt.where(User.is_blocked == is_blocked)
            
            # Пагинация и сортировка
            stmt = stmt.order_by(desc(User.registration_date)).offset(offset).limit(limit)
            
            result = await session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка пользователей: {e}")
            return []
    
    @staticmethod
    async def get_users_count(
        session: AsyncSession,
        department: Optional[Department] = None,
        is_active: Optional[bool] = None
    ) -> int:
        """Получить количество пользователей"""
        try:
            stmt = select(func.count(User.id))
            
            if department:
                stmt = stmt.where(User.department == department)
            if is_active is not None:
                stmt = stmt.where(User.is_active == is_active)
            
            result = await session.execute(stmt)
            return result.scalar() or 0
            
        except Exception as e:
            logger.error(f"Ошибка при подсчете пользователей: {e}")
            return 0
    
    @staticmethod
    async def increment_user_counter(
        session: AsyncSession,
        telegram_id: int,
        counter_type: str = "messages"  # messages или commands
    ) -> None:
        """Увеличить счетчик пользователя"""
        try:
            if counter_type == "messages":
                stmt = (
                    update(User)
                    .where(User.telegram_id == telegram_id)
                    .values(messages_count=User.messages_count + 1)
                )
            else:
                stmt = (
                    update(User)
                    .where(User.telegram_id == telegram_id)
                    .values(commands_count=User.commands_count + 1)
                )
            
            await session.execute(stmt)
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при увеличении счетчика {counter_type} для {telegram_id}: {e}")
    
    @staticmethod
    async def update_user_department(
        session: AsyncSession,
        telegram_id: int,
        department: Department
    ) -> bool:
        """Обновить отдел пользователя"""
        try:
            stmt = (
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(department=department)
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при обновлении отдела пользователя {telegram_id}: {e}")
            return False


class ActivityCRUD:
    """CRUD операции для работы с активностью пользователей"""
    
    @staticmethod
    async def log_activity(
        session: AsyncSession,
        user_id: int,
        action: str,
        section: Optional[str] = None,
        subsection: Optional[str] = None,
        details: Optional[dict] = None,
        callback_data: Optional[str] = None,
        message_text: Optional[str] = None
    ) -> None:
        """Записать активность пользователя"""
        try:
            activity = UserActivity(
                user_id=user_id,
                action=action,
                section=section,
                subsection=subsection,
                details=details,
                callback_data=callback_data,
                message_text=message_text
            )
            session.add(activity)
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при логировании активности: {e}")
    
    @staticmethod
    async def get_user_activity(
        session: AsyncSession,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[UserActivity]:
        """Получить историю активности пользователя"""
        try:
            stmt = (
                select(UserActivity)
                .where(UserActivity.user_id == user_id)
                .order_by(desc(UserActivity.timestamp))
                .offset(offset)
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении активности пользователя {user_id}: {e}")
            return []
    
    @staticmethod
    async def get_popular_sections(
        session: AsyncSession,
        days: int = 30,
        limit: int = 10
    ) -> List[tuple]:
        """Получить популярные разделы за последние N дней"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            stmt = (
                select(
                    UserActivity.section,
                    func.count(UserActivity.id).label('views')
                )
                .where(
                    and_(
                        UserActivity.timestamp >= cutoff_date,
                        UserActivity.section.isnot(None)
                    )
                )
                .group_by(UserActivity.section)
                .order_by(desc('views'))
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении популярных разделов: {e}")
            return []
    
    @staticmethod
    async def get_activity_stats(
        session: AsyncSession,
        days: int = 7
    ) -> Dict[str, Any]:
        """Получить статистику активности"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Общее количество действий
            total_stmt = (
                select(func.count(UserActivity.id))
                .where(UserActivity.timestamp >= cutoff_date)
            )
            total_actions = await session.scalar(total_stmt) or 0
            
            # Количество уникальных пользователей
            unique_users_stmt = (
                select(func.count(func.distinct(UserActivity.user_id)))
                .where(UserActivity.timestamp >= cutoff_date)
            )
            unique_users = await session.scalar(unique_users_stmt) or 0
            
            # Самые активные пользователи
            active_users_stmt = (
                select(
                    UserActivity.user_id,
                    func.count(UserActivity.id).label('actions')
                )
                .where(UserActivity.timestamp >= cutoff_date)
                .group_by(UserActivity.user_id)
                .order_by(desc('actions'))
                .limit(5)
            )
            active_users_result = await session.execute(active_users_stmt)
            active_users = active_users_result.all()
            
            return {
                "total_actions": total_actions,
                "unique_users": unique_users,
                "active_users": active_users,
                "period_days": days
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении статистики активности: {e}")
            return {}


class ContentCRUD:
    """CRUD операции для работы с контентом"""
    
    @staticmethod
    async def get_content(
        session: AsyncSession,
        key: str
    ) -> Optional[Content]:
        """Получить контент по ключу"""
        try:
            stmt = select(Content).where(
                and_(
                    Content.key == key,
                    Content.is_active == True
                )
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Ошибка при получении контента {key}: {e}")
            return None
    
    @staticmethod
    async def get_section_content(
        session: AsyncSession,
        section: str
    ) -> List[Content]:
        """Получить весь контент раздела"""
        try:
            stmt = (
                select(Content)
                .where(
                    and_(
                        Content.section == section,
                        Content.is_active == True
                    )
                )
                .order_by(Content.order_index)
            )
            result = await session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении контента раздела {section}: {e}")
            return []
    
    @staticmethod
    async def create_or_update_content(
        session: AsyncSession,
        key: str,
        section: str,
        title: Optional[str] = None,
        text: Optional[str] = None,
        media_path: Optional[str] = None,
        media_type: Optional[str] = None,
        media_file_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Content:
        """Создать или обновить контент"""
        try:
            stmt = select(Content).where(Content.key == key)
            result = await session.execute(stmt)
            content = result.scalar_one_or_none()
            
            if content:
                # Обновляем существующий контент
                content.section = section
                content.title = title or content.title
                content.text = text or content.text
                content.media_path = media_path or content.media_path
                content.media_type = media_type or content.media_type
                content.media_file_id = media_file_id or content.media_file_id
                content.tags = tags or content.tags
                content.updated_at = datetime.utcnow()
                
                logger.info(f"Обновлен контент: {key}")
            else:
                # Создаем новый контент
                content = Content(
                    key=key,
                    section=section,
                    title=title,
                    text=text,
                    media_path=media_path,
                    media_type=media_type,
                    media_file_id=media_file_id,
                    tags=tags
                )
                session.add(content)
                logger.info(f"Создан новый контент: {key}")
            
            await session.commit()
            await session.refresh(content)
            return content
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при создании/обновлении контента {key}: {e}")
            raise
    
    @staticmethod
    async def delete_content(
        session: AsyncSession,
        key: str
    ) -> bool:
        """Удалить контент (мягкое удаление)"""
        try:
            stmt = (
                update(Content)
                .where(Content.key == key)
                .values(is_active=False)
            )
            result = await session.execute(stmt)
            await session.commit()
            
            if result.rowcount > 0:
                logger.info(f"Контент {key} удален (деактивирован)")
                return True
            return False
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при удалении контента {key}: {e}")
            return False
    
    @staticmethod
    async def search_content(
        session: AsyncSession,
        query: str,
        limit: int = 10
    ) -> List[Content]:
        """Поиск контента по тексту"""
        try:
            # Простой поиск по подстроке
            search_pattern = f"%{query}%"
            
            stmt = (
                select(Content)
                .where(
                    and_(
                        or_(
                            Content.title.ilike(search_pattern),
                            Content.text.ilike(search_pattern),
                            Content.key.ilike(search_pattern)
                        ),
                        Content.is_active == True
                    )
                )
                .limit(limit)
            )
            result = await session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при поиске контента по запросу '{query}': {e}")
            return []


class AdminLogCRUD:
    """CRUD операции для логирования действий администраторов"""
    
    @staticmethod
    async def log_admin_action(
        session: AsyncSession,
        admin_id: int,
        action: str,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        details: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """Записать действие администратора"""
        try:
            log_entry = AdminLog(
                admin_id=admin_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
                success=success,
                error_message=error_message
            )
            session.add(log_entry)
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при логировании действия администратора: {e}")
    
    @staticmethod
    async def get_admin_logs(
        session: AsyncSession,
        admin_id: Optional[int] = None,
        action: Optional[str] = None,
        days: int = 30,
        limit: int = 100
    ) -> List[AdminLog]:
        """Получить логи администраторов"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            stmt = select(AdminLog).where(AdminLog.timestamp >= cutoff_date)
            
            if admin_id:
                stmt = stmt.where(AdminLog.admin_id == admin_id)
            if action:
                stmt = stmt.where(AdminLog.action == action)
            
            stmt = stmt.order_by(desc(AdminLog.timestamp)).limit(limit)
            
            result = await session.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Ошибка при получении логов администраторов: {e}")
            return []


# ========== CRIT-005 & MOD-001 FIX: Compatibility wrapper functions ==========
# These functions provide backward compatibility for handlers that expect
# standalone functions instead of CRUD classes.

async def get_all_users(limit: int = 100) -> List[Dict]:
    """Wrapper: Get all users as dict list

    ИСПРАВЛЕНИЕ КРИТИЧЕСКОЙ ОШИБКИ: Добавлены поля last_activity и registration_date в полном формате.
    Проблема: last_activity полностью отсутствовало, registration_date конвертировалось только в дату,
    из-за чего фильтрация "Активные сегодня" и "Новые пользователи" всегда возвращала пустые списки.
    """
    async for session in get_db_session():
        users = await UserCRUD.get_all_users(session, limit=limit)
        return [
            {
                "id": u.id,
                "telegram_id": u.telegram_id,
                "username": u.username,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "is_blocked": u.is_blocked,
                # ИСПРАВЛЕНИЕ: Возвращаем datetime объект для корректной фильтрации
                "registration_date": u.registration_date,
                # ИСПРАВЛЕНИЕ: Добавлено отсутствующее поле last_activity
                "last_activity": u.last_activity,
                # Для отображения в UI - форматированные строки в МСК
                "registration_date_str": format_msk_datetime(u.registration_date, "%d.%m.%Y %H:%M") + " (МСК)" if u.registration_date else "неизвестно",
                "last_activity_str": format_msk_datetime(u.last_activity, "%d.%m.%Y %H:%M") + " (МСК)" if u.last_activity else "неизвестно"
            }
            for u in users
        ]
    return []


async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict]:
    """Wrapper: Get user by telegram ID as dict

    ИСПРАВЛЕНИЕ: Добавлены поля registration_date и last_activity для корректного отображения.
    """
    async for session in get_db_session():
        user = await UserCRUD.get_user_by_telegram_id(session, telegram_id)
        if user:
            return {
                "id": user.id,
                "telegram_id": user.telegram_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_blocked": user.is_blocked,
                "block_reason": user.block_reason,
                # ИСПРАВЛЕНИЕ: Добавлены datetime объекты
                "registration_date": user.registration_date,
                "last_activity": user.last_activity,
                # Для отображения в МСК
                "registration_date_str": format_msk_datetime(user.registration_date, "%d.%m.%Y %H:%M") + " (МСК)" if user.registration_date else "неизвестно",
                "last_activity_str": format_msk_datetime(user.last_activity, "%d.%m.%Y %H:%M") + " (МСК)" if user.last_activity else "неизвестно"
            }
    return None


async def block_user(telegram_id: int, reason: Optional[str] = None) -> bool:
    """Wrapper: Block user"""
    async for session in get_db_session():
        return await UserCRUD.block_user(session, telegram_id, reason)
    return False


async def unblock_user(telegram_id: int) -> bool:
    """Wrapper: Unblock user"""
    async for session in get_db_session():
        return await UserCRUD.unblock_user(session, telegram_id)
    return False


async def get_user_activity(user_id: int, limit: int = 50) -> List[Dict]:
    """Wrapper: Get user activity as dict list"""
    async for session in get_db_session():
        activities = await ActivityCRUD.get_user_activity(session, user_id, limit)
        return [
            {
                "action": a.action,
                "section": a.section,
                "timestamp": a.timestamp.strftime("%d.%m.%Y %H:%M:%S") if a.timestamp else ""
            }
            for a in activities
        ]
    return []


async def get_statistics() -> Dict[str, Any]:
    """Wrapper: Get general statistics"""
    async for session in get_db_session():
        from datetime import datetime, timedelta
        from sqlalchemy import select, func

        # Total users
        total_users = await UserCRUD.get_users_count(session)

        # Active today
        today = datetime.utcnow().date()
        active_today_stmt = select(func.count(User.id)).where(
            func.date(User.last_activity) == today
        )
        active_today = await session.scalar(active_today_stmt) or 0

        # Active this week
        week_ago = datetime.utcnow() - timedelta(days=7)
        active_week_stmt = select(func.count(User.id)).where(
            User.last_activity >= week_ago
        )
        active_week = await session.scalar(active_week_stmt) or 0

        # New this week
        new_week_stmt = select(func.count(User.id)).where(
            User.registration_date >= week_ago
        )
        new_this_week = await session.scalar(new_week_stmt) or 0

        # Blocked users
        blocked_stmt = select(func.count(User.id)).where(User.is_blocked == True)
        blocked_users = await session.scalar(blocked_stmt) or 0

        # Activity stats
        activity_stats = await ActivityCRUD.get_activity_stats(session, days=7)

        return {
            "total_users": total_users,
            "active_today": active_today,
            "active_week": active_week,
            "new_this_week": new_this_week,
            "blocked_users": blocked_users,
            "total_actions": activity_stats.get("total_actions", 0),
            "actions_today": 0,  # TODO: Calculate
            "avg_actions_per_day": activity_stats.get("total_actions", 0) / 7 if activity_stats else 0
        }
    return {}


async def get_active_users_count() -> int:
    """Wrapper: Get count of active users"""
    async for session in get_db_session():
        return await UserCRUD.get_users_count(session, is_active=True)
    return 0


async def get_new_users_count(days: int = 7) -> int:
    """Wrapper: Get count of new users in last N days"""
    async for session in get_db_session():
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = select(func.count(User.id)).where(User.registration_date >= cutoff)
        return await session.scalar(stmt) or 0
    return 0


async def get_blocked_users() -> List[Dict]:
    """Wrapper: Get blocked users"""
    async for session in get_db_session():
        users = await UserCRUD.get_all_users(session, is_blocked=True, limit=100)
        return [
            {
                "telegram_id": u.telegram_id,
                "username": u.username,
                "first_name": u.first_name,
                "block_reason": u.block_reason
            }
            for u in users
        ]
    return []


async def get_section_statistics(days: int = 30) -> List[tuple]:
    """
    Wrapper: Get popular sections statistics

    ИСПРАВЛЕНИЕ: Добавлено логирование для диагностики
    """
    async for session in get_db_session():
        logger.info(f"📊 Запрос популярных разделов за последние {days} дней")
        result = await ActivityCRUD.get_popular_sections(session, days=days)
        logger.info(f"✅ Получено {len(result)} популярных разделов: {result}")
        return result
    return []


async def log_user_activity(
    user_id: int,
    action: str,
    section: Optional[str] = None,
    subsection: Optional[str] = None,
    details: Optional[dict] = None,
    callback_data: Optional[str] = None,
    message_text: Optional[str] = None
) -> None:
    """
    MOD-001 FIX: Wrapper for logging user activity
    Calls ActivityCRUD.log_activity with proper session management

    ИСПРАВЛЕНИЕ: Добавлены все параметры для полного логирования активности
    """
    try:
        async for session in get_db_session():
            await ActivityCRUD.log_activity(
                session=session,
                user_id=user_id,
                action=action,
                section=section,
                subsection=subsection,
                details=details,
                callback_data=callback_data,
                message_text=message_text
            )
            logger.debug(f"✅ Активность залогирована: user_id={user_id}, action={action}, section={section}")
    except Exception as e:
        logger.error(f"❌ Ошибка логирования активности: {e}", exc_info=True)


async def get_recent_activity(limit: int = 50) -> List[Dict]:
    """
    MVP FEATURE: Получить последние N действий пользователей.

    PERF-001 FIX: Added eager loading to avoid N+1 queries

    Args:
        limit: Количество записей для выборки

    Returns:
        List[Dict]: Список словарей с информацией об активности
    """
    async for session in get_db_session():
        try:
            # PERF-001 FIX: Use selectinload for eager loading
            stmt = (
                select(UserActivity)
                .options(selectinload(UserActivity.user))
                .order_by(desc(UserActivity.timestamp))
                .limit(limit)
            )
            result = await session.execute(stmt)
            activities = result.scalars().all()

            # TIMEZONE: Конвертируем timestamp из UTC в московское время (МСК)
            # PERF-001 FIX: Access user via eager-loaded relationship
            return [
                {
                    "id": activity.id,
                    "user_id": activity.user_id,
                    "telegram_id": activity.user.telegram_id,
                    "username": activity.user.username or "без username",
                    "first_name": activity.user.first_name or "Пользователь",
                    "action": activity.action,
                    "section": activity.section or "-",
                    "subsection": activity.subsection or "-",
                    "timestamp": activity.timestamp,
                    # TIMEZONE: Время отображается в МСК для удобства пользователей
                    "timestamp_str": format_msk_datetime(activity.timestamp) if activity.timestamp else "-"
                }
                for activity in activities
            ]
        except Exception as e:
            logger.error(f"❌ Ошибка при получении последней активности: {e}", exc_info=True)
            return []
    return []


async def get_all_activity_for_export(days: int = 30) -> List[Dict]:
    """
    MVP FEATURE: Получить всю активность за последние N дней для экспорта.

    PERF-001 FIX: Added eager loading to avoid N+1 queries

    Args:
        days: Количество дней для выборки

    Returns:
        List[Dict]: Список словарей с информацией об активности
    """
    async for session in get_db_session():
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # PERF-001 FIX: Use selectinload for eager loading
            stmt = (
                select(UserActivity)
                .options(selectinload(UserActivity.user))
                .where(UserActivity.timestamp >= cutoff_date)
                .order_by(desc(UserActivity.timestamp))
            )
            result = await session.execute(stmt)
            activities = result.scalars().all()

            # TIMEZONE: Конвертируем timestamp из UTC в московское время (МСК) для экспорта
            # PERF-001 FIX: Access user via eager-loaded relationship
            return [
                {
                    "id": activity.id,
                    "telegram_id": activity.user.telegram_id,
                    "username": activity.user.username or "",
                    "first_name": activity.user.first_name or "",
                    "last_name": activity.user.last_name or "",
                    "action": activity.action,
                    "section": activity.section or "",
                    "subsection": activity.subsection or "",
                    "callback_data": activity.callback_data or "",
                    # TIMEZONE: Время экспорта в МСК для удобства чтения администраторами
                    "timestamp": format_msk_datetime(activity.timestamp) if activity.timestamp else ""
                }
                for activity in activities
            ]
        except Exception as e:
            logger.error(f"❌ Ошибка при получении активности для экспорта: {e}", exc_info=True)
            return []
    return []


async def get_date_statistics(days: int = 30) -> Dict:
    """
    MVP FEATURE: Получить статистику по датам за последние N дней.

    Возвращает:
    - Статистику по дням недели (пн-вс)
    - Топ-5 самых активных дней
    - Статистику по часам (пиковые часы)
    - Уникальные пользователи и действия по дням

    Args:
        days: Количество дней для анализа

    Returns:
        Dict: Словарь со статистикой
    """
    async for session in get_db_session():
        try:
            from collections import defaultdict
            cutoff_date = datetime.utcnow() - timedelta(days=days)

            # Получаем всю активность за период
            stmt = (
                select(UserActivity)
                .where(UserActivity.timestamp >= cutoff_date)
                .order_by(UserActivity.timestamp)
            )
            result = await session.execute(stmt)
            activities = result.scalars().all()

            if not activities:
                return {
                    "has_data": False,
                    "days_analyzed": days
                }

            # Подсчет по дням недели (0=Пн, 6=Вс)
            weekday_counts = defaultdict(int)
            weekday_users = defaultdict(set)

            # Подсчет по конкретным датам
            daily_counts = defaultdict(int)
            daily_users = defaultdict(set)

            # Подсчет по часам
            hourly_counts = defaultdict(int)

            # TIMEZONE: Конвертируем все timestamp в московское время для корректной группировки
            for activity in activities:
                if not activity.timestamp:
                    continue

                # TIMEZONE: Конвертируем UTC -> МСК для правильного определения дня недели, даты и часа
                msk_time = utc_to_msk(activity.timestamp)
                if not msk_time:
                    continue

                # День недели (по московскому времени)
                weekday = msk_time.weekday()
                weekday_counts[weekday] += 1
                weekday_users[weekday].add(activity.user_id)

                # Конкретная дата (по московскому времени)
                date_key = msk_time.strftime("%Y-%m-%d")
                daily_counts[date_key] += 1
                daily_users[date_key].add(activity.user_id)

                # Час дня (по московскому времени)
                hour = msk_time.hour
                hourly_counts[hour] += 1

            # Формируем результат
            weekday_names = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            weekday_stats = [
                {
                    "weekday": weekday_names[day],
                    "actions": weekday_counts[day],
                    "unique_users": len(weekday_users[day])
                }
                for day in range(7)
            ]

            # Топ-5 самых активных дней
            top_days = sorted(
                [
                    {
                        "date": date,
                        "actions": count,
                        "unique_users": len(daily_users[date])
                    }
                    for date, count in daily_counts.items()
                ],
                key=lambda x: x["actions"],
                reverse=True
            )[:5]

            # Топ-3 пиковых часа
            top_hours = sorted(
                [
                    {"hour": hour, "actions": count}
                    for hour, count in hourly_counts.items()
                ],
                key=lambda x: x["actions"],
                reverse=True
            )[:3]

            total_actions = len(activities)
            unique_users = len(set(a.user_id for a in activities if a.user_id))

            logger.info(f"✅ Статистика по датам: {total_actions} действий, {unique_users} уникальных пользователей")

            return {
                "has_data": True,
                "days_analyzed": days,
                "total_actions": total_actions,
                "unique_users": unique_users,
                "weekday_stats": weekday_stats,
                "top_days": top_days,
                "top_hours": top_hours
            }

        except Exception as e:
            logger.error(f"❌ Ошибка при получении статистики по датам: {e}", exc_info=True)
            return {"has_data": False, "error": str(e)}
    return {"has_data": False}


async def get_users_for_export() -> List[Dict]:
    """
    MVP FEATURE: Получить список всех пользователей для экспорта в Excel/CSV.

    Returns:
        List[Dict]: Список словарей с данными пользователей
    """
    async for session in get_db_session():
        try:
            stmt = select(User).order_by(User.registration_date.desc())
            result = await session.execute(stmt)
            users = result.scalars().all()

            logger.info(f"📊 Экспорт пользователей: найдено {len(users)} пользователей в БД")

            if not users:
                logger.warning("⚠️ Нет пользователей для экспорта!")
                return []

            # TIMEZONE: Конвертируем все даты из UTC в московское время (МСК)
            users_list = [
                {
                    "id": user.id,
                    "telegram_id": user.telegram_id,
                    "username": user.username or "",
                    "first_name": user.first_name or "",
                    "last_name": user.last_name or "",
                    "phone": user.phone or "",
                    # TIMEZONE: Даты конвертируются из UTC в МСК для отображения
                    "registration_date": format_msk_datetime(user.registration_date) if user.registration_date else "",
                    "last_activity": format_msk_datetime(user.last_activity) if user.last_activity else "",
                    "is_blocked": "Да" if user.is_blocked else "Нет",
                    "is_admin": "Да" if user.is_admin else "Нет"
                }
                for user in users
            ]

            logger.info(f"✅ Сформирован список из {len(users_list)} пользователей для экспорта")
            return users_list

        except Exception as e:
            logger.error(f"❌ Ошибка при получении пользователей для экспорта: {e}", exc_info=True)
            return []
    return []


# Экспорт классов и wrapper functions
__all__ = [
    # CRUD Classes
    "UserCRUD",
    "ActivityCRUD",
    "ContentCRUD",
    "AdminLogCRUD",
    # Compatibility wrappers for admin.py
    "get_all_users",
    "get_user_by_telegram_id",
    "block_user",
    "unblock_user",
    "get_user_activity",
    "get_statistics",
    "get_active_users_count",
    "get_new_users_count",
    "get_blocked_users",
    "get_section_statistics",
    "log_user_activity",
    # MVP FEATURES: Activity logs
    "get_recent_activity",
    "get_all_activity_for_export",
    # MVP FEATURES: Date statistics and Excel export
    "get_date_statistics",
    "get_users_for_export"
]

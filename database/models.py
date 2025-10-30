"""
Модели базы данных SQLAlchemy
"""

from datetime import datetime
from typing import Optional, List
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, 
    ForeignKey, Text, Float, Enum, JSON, Index
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс для всех моделей с поддержкой асинхронности"""
    pass


class Department(PyEnum):
    """Отделы компании"""
    GENERAL = "general"
    SALES = "sales"
    SPORT = "sport"
    ADMIN = "admin"


class UserRole(PyEnum):
    """Роли пользователей"""
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"
    SUPER_ADMIN = "super_admin"


class User(Base):
    """Модель пользователя бота"""
    __tablename__ = 'users'
    
    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Telegram data
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    language_code: Mapped[Optional[str]] = mapped_column(String(10), default="ru")
    
    # User info
    department: Mapped[Optional[str]] = mapped_column(
        Enum(Department, native_enum=False, length=50), 
        nullable=True
    )
    role: Mapped[str] = mapped_column(
        Enum(UserRole, native_enum=False, length=50), 
        default=UserRole.USER
    )
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    park_location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Status
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    block_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    registration_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_activity: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Statistics
    messages_count: Mapped[int] = mapped_column(Integer, default=0)
    commands_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    # PERF FIX: Changed lazy="selectin" to lazy="noload" to prevent N+1 queries
    # Previously, every user fetch was loading ALL activities, test_results, admin_logs
    # causing 150-400ms delays. Now relationships only load when explicitly requested.
    activities: Mapped[List["UserActivity"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload"
    )
    test_results: Mapped[List["TestResult"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="noload"
    )
    admin_logs: Mapped[List["AdminLog"]] = relationship(
        back_populates="admin",
        cascade="all, delete-orphan",
        lazy="noload"
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})>"
    
    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""
        parts = []
        if self.first_name:
            parts.append(self.first_name)
        if self.last_name:
            parts.append(self.last_name)
        return " ".join(parts) if parts else f"User {self.telegram_id}"
    
    @property
    def mention(self) -> str:
        """Упоминание пользователя для Telegram"""
        if self.username:
            return f"@{self.username}"
        return self.full_name


class UserActivity(Base):
    """Модель для отслеживания активности пользователей"""
    __tablename__ = 'user_activity'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    
    # Activity info
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    section: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    subsection: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Additional data
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    callback_data: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    user: Mapped["User"] = relationship(back_populates="activities")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_user_activity_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_user_activity_action_section', 'action', 'section'),
    )
    
    def __repr__(self):
        return f"<UserActivity(user_id={self.user_id}, action={self.action}, timestamp={self.timestamp})>"


class Content(Base):
    """Модель для хранения контента бота"""
    __tablename__ = 'content'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Content identification
    section: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Content data
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Metadata
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    def __repr__(self):
        return f"<Content(section={self.section}, key={self.key})>"


class TestQuestion(Base):
    """Модель для вопросов тестирования"""
    __tablename__ = 'test_questions'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Question info
    category: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Options (stored as JSON array)
    options: Mapped[List[str]] = mapped_column(JSON, nullable=False)
    correct_answer_index: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Additional info
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty: Mapped[int] = mapped_column(Integer, default=1)  # 1-5
    points: Mapped[int] = mapped_column(Integer, default=10)
    
    # Media
    image_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # Relationships
    test_answers: Mapped[List["TestAnswer"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<TestQuestion(category={self.category}, question={self.question[:50]}...)>"


class TestResult(Base):
    """Модель для результатов тестирования"""
    __tablename__ = 'test_results'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    
    # Test info
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False)
    correct_answers: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Status
    is_passed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="test_results")
    answers: Mapped[List["TestAnswer"]] = relationship(
        back_populates="test_result",
        cascade="all, delete-orphan"
    )
    
    # Index for performance
    __table_args__ = (
        Index('idx_test_results_user_category', 'user_id', 'category'),
    )
    
    def __repr__(self):
        return f"<TestResult(user_id={self.user_id}, category={self.category}, score={self.score})>"


class TestAnswer(Base):
    """Модель для ответов на вопросы тестирования"""
    __tablename__ = 'test_answers'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    test_result_id: Mapped[int] = mapped_column(
        ForeignKey('test_results.id'), 
        nullable=False, 
        index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey('test_questions.id'), 
        nullable=False, 
        index=True
    )
    
    # Answer info
    selected_answer_index: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamp
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    test_result: Mapped["TestResult"] = relationship(back_populates="answers")
    question: Mapped["TestQuestion"] = relationship(back_populates="test_answers")
    
    def __repr__(self):
        return f"<TestAnswer(question_id={self.question_id}, is_correct={self.is_correct})>"


class AdminLog(Base):
    """Модель для логирования действий администраторов"""
    __tablename__ = 'admin_logs'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False, index=True)
    
    # Action info
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Details
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    
    # Status
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship
    admin: Mapped["User"] = relationship(back_populates="admin_logs")
    
    def __repr__(self):
        return f"<AdminLog(admin_id={self.admin_id}, action={self.action}, timestamp={self.timestamp})>"


class BroadcastMessage(Base):
    """Модель для массовых рассылок"""
    __tablename__ = 'broadcast_messages'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    
    # Message info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    
    # Target
    target_department: Mapped[Optional[str]] = mapped_column(
        Enum(Department, native_enum=False, length=50),
        nullable=True
    )
    target_role: Mapped[Optional[str]] = mapped_column(
        Enum(UserRole, native_enum=False, length=50),
        nullable=True
    )
    
    # Statistics
    total_recipients: Mapped[int] = mapped_column(Integer, default=0)
    sent_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="pending")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<BroadcastMessage(title={self.title}, status={self.status})>"


class SystemSettings(Base):
    """Модель для системных настроек"""
    __tablename__ = 'system_settings'
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), default="string")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    def __repr__(self):
        return f"<SystemSettings(key={self.key}, value={self.value})>"

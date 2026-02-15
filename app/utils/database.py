# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import asyncio
from contextlib import asynccontextmanager
import subprocess
from datetime import datetime
from typing import Optional

import sqlalchemy as db
from envparse import Env
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker


env = Env()
env.read_envfile()

Base = declarative_base()
DATABASE_URL = f'postgresql+asyncpg://{env.str("PG_USER")}:{env.str("PG_PASSWORD")}@{env.str("PG_HOST")}:{env.str("PG_PORT")}/{env.str("PG_DB")}'

_engine = None
_session_factory = None

async def init_database():
    """Инициализация подключения к БД (вызывается один раз в main)"""
    global _engine, _session_factory
    
    if _engine is not None:
        return _engine, _session_factory
    
    db_url_for_log = f'postgresql+asyncpg://{env.str("PG_USER")}:****@{env.str("PG_HOST")}:{env.str("PG_PORT")}/{env.str("PG_DB")}'
    logger.info(f"Initializing database connection: {db_url_for_log}")
    
    try:
        _engine = create_async_engine(DATABASE_URL, echo=False)
        logger.debug("Async database engine created successfully")
    except Exception as e:
        logger.exception(f"Failed to create database engine: {e}")
        raise
    
    _session_factory = sessionmaker(
        bind=_engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    logger.debug("Async session factory created")
    
    return _engine, _session_factory

async def get_session() -> AsyncSession:
    """
    Получение сессии БД.
    Использование: async with await get_session() as session:
    """
    if _session_factory is None:
        await init_database()
    
    return _session_factory()

async def get_engine():
    """Получение engine (для создания таблиц и миграций)"""
    if _engine is None:
        await init_database()
    return _engine

@asynccontextmanager
async def session_scope():
    """Контекстный менеджер для автоматического коммита/роллбека"""
    session = await get_session()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

async def close_database():
    """Закрытие соединения с БД"""
    global _engine
    if _engine:
        await _engine.dispose()
        logger.info("Database connection closed")
        _engine = None
        _session_factory = None

async def close_database_connections():
    """Закрытие всех соединений с БД"""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        logger.info("Database connections closed")
        _engine = None
        _session_factory = None


async def run_migrations():
    logger.info("Starting database migrations...")

    try:
        revision_message = (
            f"Auto migration {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(f"Creating autogenerate revision: {revision_message}")

        result_revision = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", revision_message],
            check=False,
            capture_output=True,
            text=True,
        )

        if result_revision.returncode == 0:
            if result_revision.stdout:
                logger.info(f"Revision created: {result_revision.stdout.strip()}")
            else:
                logger.info("No changes detected, revision not created")
        else:
            if "Target database is not up to date" in result_revision.stderr:
                logger.warning("Database not up to date, skipping autogenerate")
            else:
                logger.error(f"Failed to create revision: {result_revision.stderr}")

        logger.info("Applying migrations to head...")
        result_upgrade = subprocess.run(
            ["alembic", "upgrade", "head"], check=True, capture_output=True, text=True
        )

        logger.success(f"Migrations completed successfully")
        if result_upgrade.stdout:
            logger.debug(f"Migration output: {result_upgrade.stdout}")

    except subprocess.CalledProcessError as e:
        logger.error(f"Migration command failed with exit code {e.returncode}")
        logger.error(f"Error output: {e.stderr}")
        logger.exception("Migration error details:")
        raise
    except FileNotFoundError:
        logger.error("Alembic not found. Make sure it's installed and in PATH")
        logger.info("Try running: pip install alembic")
        raise
    except Exception as e:
        logger.exception(f"Unexpected error during migrations: {e}")
        raise


class User(Base):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, unique=True)
    token = db.Column(db.Text, nullable=True)
    profile_id = db.Column(db.Integer, nullable=True)
    role = db.Column(db.String, nullable=True)
    person_id = db.Column(db.String, nullable=True)
    student_id = db.Column(db.BigInteger, nullable=True, unique=True)
    contract_id = db.Column(db.BigInteger, nullable=True)
    settings = relationship("Settings", backref="user", cascade="all, delete-orphan")
    active = db.Column(db.Boolean, default=True)


class AuthData(Base):
    __tablename__ = "auth_data"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    auth_method = db.Column(db.String, nullable=True)
    token_expired_at = db.Column(db.DateTime, nullable=True)
    token_for_refresh = db.Column(db.String, nullable=True)
    client_id = db.Column(db.String, nullable=True)
    client_secret = db.Column(db.String, nullable=True)


class Event(Base):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.BigInteger, nullable=False)
    event_type = db.Column(db.String, nullable=False)
    subject_name = db.Column(db.String, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    teacher_id = db.Column(db.BigInteger, nullable=False)


# Таблица для сохранения уведомлений, которые созданы ботом и не приходят с API МЭШ
class BotNotification(Base):
    __tablename__ = "bot_notifications"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    type = db.Column(db.String, nullable=False)
    text = db.Column(db.String, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(), nullable=False)


class Settings(Base):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    enable_new_mark_notification = db.Column(db.Boolean, default=True)
    enable_homework_notification = db.Column(db.Boolean, default=True)
    skip_empty_days_schedule = db.Column(db.Boolean, default=True)
    skip_empty_days_homeworks = db.Column(db.Boolean, default=True)
    next_day_if_lessons_end_schedule = db.Column(db.Boolean, default=True)
    next_day_if_lessons_end_homeworks = db.Column(db.Boolean, default=True)
    enable_homework_done_function = db.Column(db.Boolean, default=True)
    experimental_features = db.Column(db.Boolean, default=False)

    # Exremental features
    use_cache = db.Column(db.Boolean, default=False)


class SettingDefinition(Base):
    __tablename__ = "setting_definitions"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String, unique=True, nullable=False)
    label = db.Column(db.String, nullable=False)
    type = db.Column(db.String(32), default="bool")
    ordering = db.Column(db.Integer, default=0)
    visible = db.Column(db.Boolean, default=True)
    experimental = db.Column(db.Boolean, default=False)


class UserData(Base):
    __tablename__ = "user_data"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    first_name = db.Column(db.String, nullable=True)
    last_name = db.Column(db.String, nullable=True)
    middle_name = db.Column(db.String, nullable=True)
    gender = db.Column(db.String, nullable=True)
    phone = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=True)
    birthday = db.Column(db.DateTime, nullable=True)
    username = db.Column(db.String, nullable=True)


class PremiumSubscriptionPlan(Base):
    __tablename__ = "premium_subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, nullable=False)
    title = db.Column(db.String, nullable=False)
    text_name = db.Column(db.String, nullable=False)
    price = db.Column(db.Integer, nullable=False)
    duration = db.Column(db.Integer, nullable=False)
    ordering = db.Column(db.Integer, default=0)
    show_in_menu = db.Column(db.Boolean, default=True)

    subscriptions = relationship("PremiumSubscription", back_populates="plan_obj")


class PremiumSubscription(Base):
    __tablename__ = "premium_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    balance = db.Column(db.Float, default=0)
    plan = db.Column(
        db.Integer, db.ForeignKey("premium_subscription_plans.id"), nullable=True
    )
    auto_renew = db.Column(db.Boolean, default=True)

    plan_obj = relationship("PremiumSubscriptionPlan", back_populates="subscriptions")


class Transaction(Base):
    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    operation_type = db.Column(db.String(25), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime(timezone=False), default=datetime.now())
    telegram_transaction_id = db.Column(db.String, nullable=True)


class Homework(Base):
    __tablename__ = "homeworks"

    id = db.Column(db.Integer, primary_key=True)
    task = db.Column(db.String, nullable=False)
    subject_id = db.Column(db.Integer, nullable=False)


class Gdz(Base):
    __tablename__ = "gdz"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id = db.Column(db.Integer, nullable=True)
    subject_name = db.Column(db.String, nullable=True)
    book_url = db.Column(db.String, nullable=True)
    search_by = db.Column(db.String, nullable=True)


class StudentBook(Base):
    __tablename__ = "student_books"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_id = db.Column(db.Integer, nullable=True)
    subject_name = db.Column(db.String, nullable=True)
    file = db.Column(db.String, nullable=True)

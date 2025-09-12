import logging
import subprocess
from datetime import datetime

import pytz
import sqlalchemy as db
from envparse import Env
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from alembic import command
from alembic.config import Config

env = Env()
env.read_envfile()

Base = declarative_base()
DATABASE_URL = f'postgresql+asyncpg://{env.str("PG_USER")}:{env.str("PG_PASSWORD")}@{env.str("PG_HOST")}:{env.str("PG_PORT")}/{env.str("PG_DB")}'
engine_db = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(
    bind=engine_db, class_=AsyncSession, expire_on_commit=False
)


async def run_migrations():
    try:
        result = subprocess.run(
            ["alembic", "revision", f'--message="{datetime.now()}"', "--autogenerate"]
        )
        result = subprocess.run(
            ["alembic", "upgrade", "head"], check=True, capture_output=True, text=True
        )
        logging.info(f"Migrations completed: {result.stdout}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Error during migrations: {e.stderr}")
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

import sqlalchemy as db
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

import pytz
from datetime import datetime
from alembic import command
from alembic.config import Config
import logging
import subprocess
from envparse import Env


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
    token = db.Column(db.Text, nullable=False)
    profile_id = db.Column(db.Integer, nullable=True)
    role = db.Column(db.String, nullable=True)
    person_id = db.Column(db.String, nullable=True)
    student_id = db.Column(db.BigInteger, nullable=True, unique=True)
    contract_id = db.Column(db.BigInteger, nullable=True)
    settings = relationship("Settings", backref="user", cascade="all, delete-orphan")


class Event(Base):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    student_id = db.Column(db.BigInteger, nullable=False)
    event_type = db.Column(db.String, nullable=False)
    subject_name = db.Column(db.String, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    teacher_id = db.Column(db.BigInteger, nullable=False)


# БД для сохранения уведомлений, которые созданы ботом и не приходят с API МЭШ
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
    experimental_features = db.Column(db.Boolean, default=False)

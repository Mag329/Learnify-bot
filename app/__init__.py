from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
from envparse import Env
import locale

from config import *

from app.handlers.user import (
    auth,
    marks,
    homeworks,
    notifications,
    settings,
    schedule,
    menu,
    results,
    other,
)
from app.handlers.admin import panel
from app.middlewares.middlewares import AllowedUsersMiddleware, CheckUserInDbMiddleware, LoggingMiddleware
from app.middlewares.stats import StatsMiddleware
from app.utils.database import Base, engine_db, run_migrations
import app.keyboards.user.keyboards as kb


env = Env()
env.read_envfile()

bot = Bot(
    token=env.str("TOKEN"),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()


locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")


async def on_startup():
    await bot.send_message(
        env.str("OWNER_ID"), "Бот запущен", reply_markup=kb.delete_message
    )


async def on_stop():
    await bot.send_message(
        env.str("OWNER_ID"), "Бот остановлен", reply_markup=kb.delete_message
    )


async def main():
    logging.info("Starting bot...")

    if env.bool("USE_ALEMBIC", default=False):
        logging.info("Run migrations...")
        try:
            await run_migrations()
        except Exception as e:
            logging.critical(f"Error during migrations: {e}")
            return

    async with engine_db.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logging.info("Setting bot...")

    if not env.bool("DEV", default=False):
        dp.startup.register(on_startup)
        dp.shutdown.register(on_stop)

    # User
    dp.include_router(auth.router)
    dp.include_router(marks.router)
    dp.include_router(homeworks.router)
    dp.include_router(notifications.router)
    dp.include_router(settings.router)
    dp.include_router(schedule.router)
    dp.include_router(menu.router)
    dp.include_router(results.router)

    # Admin
    dp.include_router(panel.router)

    dp.include_router(other.router)

    # dp.message.middleware(AllowedUsersMiddleware())
    # dp.callback_query.middleware(AllowedUsersMiddleware())

    # dp.message.middleware(CheckUserInDbMiddleware())
    
    # dp.message.middleware(LoggingMiddleware())
    # dp.callback_query.middleware(LoggingMiddleware())
    
    dp.update.middleware(LoggingMiddleware())
    
    dp.update.middleware(StatsMiddleware())

    await bot.delete_webhook(drop_pending_updates=True)

    from app.utils.checkers import new_notifications_checker, replaced_checker

    await new_notifications_checker(bot)
    scheduler.add_job(new_notifications_checker, "interval", minutes=1, args=(bot,))

    # await replaced_checker(bot)
    # scheduler.add_job(replaced_checker, "interval", minutes=10, args=(bot,))

    scheduler.start()

    logging.info("Polling bot...")
    await dp.start_polling(bot)

import asyncio
import locale
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from envparse import Env
from pytz import timezone

import app.keyboards.user.keyboards as kb
from app.config.config import *
from app.handlers.admin import panel, payment
from app.handlers.user import (auth, homeworks, inline_mode, marks, menu,
                               notifications, other, results, schedule,
                               settings, subscription, gdz)
from app.middlewares.middlewares import AllowedUsersMiddleware, CheckSubscription, LoggingMiddleware
from app.middlewares.stats import StatsMiddleware
from app.utils.database import Base, engine_db, run_migrations
from app.utils.misc import (create_premium_subscription_plans_if_not_exists,
                            create_settings_definitions_if_not_exists)
from app.utils.scheduler import scheduler
from app.utils.user.api.learnify.subscription import restore_renew_subscription_jobs

env = Env()
env.read_envfile()

bot = Bot(
    token=env.str("TOKEN"),
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML, link_preview_is_disabled=True
    ),
)
dp = Dispatcher(storage=MemoryStorage())

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
    if LEARNIFY_API_TOKEN:
        dp.include_router(subscription.router)
        dp.include_router(gdz.router)
    # dp.include_router(inline_mode.router)

    # Admin
    dp.include_router(panel.router)
    dp.include_router(payment.router)

    dp.include_router(other.router)

    # Middlewares
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(StatsMiddleware())
    dp.update.middleware(CheckSubscription())
    
    if ONLY_ALLOWED_USERS:
        dp.update.middleware(AllowedUsersMiddleware())

    await bot.delete_webhook(drop_pending_updates=True)

    from app.utils.checkers import (birthday_checker,
                                    new_notifications_checker,
                                    replaced_checker)
    from app.utils.user.api.mes.auth import restore_refresh_tokens_jobs

    await create_settings_definitions_if_not_exists()
    
    if LEARNIFY_API_TOKEN:
        await create_premium_subscription_plans_if_not_exists()

    await new_notifications_checker(bot)
    scheduler.add_job(new_notifications_checker, "interval", minutes=1, args=(bot,))

    await restore_refresh_tokens_jobs(bot)
    await restore_renew_subscription_jobs(bot)

    if env.bool("USE_GIGACHAT", default=False):
        await birthday_checker(bot)
        scheduler.add_job(
            birthday_checker, trigger="cron", hour=10, minute=0, args=(bot,)
        )
        
    from app.minio import init_bucket
    
    await init_bucket()

    # await replaced_checker(bot)
    # scheduler.add_job(replaced_checker, "interval", minutes=10, args=(bot,))

    scheduler.start()

    from app.config import config

    config.BOT_USERNAME = (await bot.me()).username

    logging.info("Polling bot...")
    await dp.start_polling(bot)

import asyncio
import locale

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp_socks import ProxyConnector
from envparse import Env
from loguru import logger

import app.keyboards.user.keyboards as kb
from app.config.config import *
from app.handlers.admin import panel, payment
from app.handlers.user import (
    auth,
    homeworks,
    marks,
    menu,
    notifications,
    other,
    results,
    schedule,
    settings,
)
from app.handlers.user.premium import router as premium_router
from app.middlewares.middlewares import (
    AllowedUsersMiddleware,
    CheckSubscription,
    LoggingMiddleware,
    UpdateUsernameMiddleware,
)
from app.middlewares.stats import StatsMiddleware
from app.utils.database import Base, get_session, run_migrations, init_database
from app.utils.misc import (
    create_premium_subscription_plans_if_not_exists,
    create_settings_definitions_if_not_exists,
)
from app.utils.scheduler import scheduler
from app.utils.user.api.learnify.subscription import restore_renew_subscription_jobs

env = Env()
env.read_envfile()


dp = Dispatcher(storage=MemoryStorage())
bot = None

try:
    locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
except locale.Error:
    logger.warning("Russian locale not available, using default")


async def on_startup(bot: Bot):
    await bot.send_message(
        env.str("OWNER_ID"), "Бот запущен", reply_markup=kb.delete_message
    )
    logger.info("Bot started successfully")


async def on_stop(bot: Bot):
    await bot.send_message(
        env.str("OWNER_ID"), "Бот остановлен", reply_markup=kb.delete_message
    )
    logger.info("Bot stopped")


async def main():
    logger.info("Starting bot...")
    
    client_session = None
    polling_task = None

    # Настройка прокси
    if TG_PROXY:
        logger.info(f"Using proxy: {TG_PROXY}")
        if TG_PROXY.startswith("http"):
            session = AiohttpSession(proxy=TG_PROXY)
        elif TG_PROXY.startswith("socks5"):
            try:
                connector = ProxyConnector.from_url(TG_PROXY)
                client_session = aiohttp.ClientSession(connector=connector)
                session = AiohttpSession(client_session=client_session)
                logger.debug("SOCKS5 proxy configured successfully")
            except Exception as e:
                logger.error(f"Failed to configure SOCKS5 proxy: {e}")
                session = AiohttpSession()
    else:
        logger.debug("No proxy configured")
        session = AiohttpSession()

    # Создание бота
    try:
        bot = Bot(
            token=env.str("TOKEN"),
            session=session,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML, link_preview_is_disabled=True
            ),
        )
        logger.info("Bot instance created")
    except Exception as e:
        logger.exception(f"Failed to create bot instance: {e}")
        return

    # Инициализация подключения к БД
    await init_database()
    
    # Миграции базы данных
    if env.bool("USE_ALEMBIC", default=False):
        logger.info("Run migrations...")
        try:
            await run_migrations()
            logger.info("Migrations completed successfully")
        except Exception as e:
            logger.critical(f"Error during migrations: {e}")
            return

    # Создание таблиц
    from app.utils.database import get_engine
    
    try:
        engine = await get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")
    except Exception as e:
        logger.exception(f"Error creating database tables: {e}")
        return

    logger.info("Setting up bot handlers and middlewares...")

    # Регистрация обработчиков запуска/остановки
    if not env.bool("DEV", default=False):
        dp.startup.register(on_startup)
        dp.shutdown.register(on_stop)
        logger.debug("Startup/shutdown handlers registered")

    # User handlers
    dp.include_router(auth.router)
    dp.include_router(marks.router)
    dp.include_router(homeworks.router)
    dp.include_router(notifications.router)
    dp.include_router(settings.router)
    dp.include_router(schedule.router)
    dp.include_router(menu.router)
    dp.include_router(results.router)
    if LEARNIFY_API_TOKEN:
        dp.include_router(premium_router)
        logger.info("Premium router included")

    # dp.include_router(inline_mode.router)

    # Admin handlers
    dp.include_router(panel.router)
    dp.include_router(payment.router)

    dp.include_router(other.router)

    logger.debug(f"Total routers included: {len(dp.sub_routers)}")

    # Middlewares
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(StatsMiddleware())
    dp.update.middleware(CheckSubscription())
    dp.update.middleware(UpdateUsernameMiddleware())

    if ONLY_ALLOWED_USERS:
        dp.update.middleware(AllowedUsersMiddleware())
        logger.info("Allowed users middleware enabled")

    # Удаление вебхука
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted, pending updates dropped")
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")

    # Импорт и настройка проверок
    from app.utils.checkers import (
        birthday_checker,
        new_notifications_checker,
    )
    from app.utils.user.api.mes.auth import restore_refresh_tokens_jobs

    # Создание настроек
    try:
        await create_settings_definitions_if_not_exists()
        logger.info("Settings definitions created/verified")
    except Exception as e:
        logger.error(f"Error creating settings definitions: {e}")

    # Создание планов подписки
    if LEARNIFY_API_TOKEN:
        try:
            await create_premium_subscription_plans_if_not_exists()
            logger.info("Premium subscription plans created/verified")
        except Exception as e:
            logger.error(f"Error creating subscription plans: {e}")

    # Настройка проверок и задач
    try:
        await new_notifications_checker(bot)
        scheduler.add_job(new_notifications_checker, "interval", minutes=1, args=(bot,))
        logger.info("Notifications checker scheduled")
    except Exception as e:
        logger.error(f"Error setting up notifications checker: {e}")

    try:
        await restore_refresh_tokens_jobs(bot)
        logger.info("Token refresh jobs restored")
    except Exception as e:
        logger.error(f"Error restoring token refresh jobs: {e}")

    try:
        await restore_renew_subscription_jobs(bot)
        logger.info("Subscription renew jobs restored")
    except Exception as e:
        logger.error(f"Error restoring subscription renew jobs: {e}")

    # await replaced_checker(bot)
    # scheduler.add_job(replaced_checker, "interval", minutes=10, args=(bot,))

    # Настройка GigaChat
    if env.bool("USE_GIGACHAT", default=False):
        try:
            await birthday_checker(bot)
            scheduler.add_job(
                birthday_checker, trigger="cron", hour=10, minute=0, args=(bot,)
            )
            logger.info("Birthday checker scheduled with GigaChat")
        except Exception as e:
            logger.error(f"Error setting up birthday checker: {e}")

    # Инициализация MinIO
    try:
        from app.minio import init_minio, init_bucket

        await init_minio()
        await init_bucket()
        logger.info("MinIO bucket initialized")
    except Exception as e:
        logger.error(f"Error initializing MinIO bucket: {e}")

    # Запуск планировщика
    try:
        scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error(f"Error starting scheduler: {e}")

    # Основной цикл бота
    try:
        from app.config import config

        bot_info = await bot.me()
        config.BOT_USERNAME = bot_info.username

        logger.info(
            f"Bot @{bot_info.username} (ID: {bot_info.id}) is starting polling..."
        )
        polling_task = asyncio.create_task(dp.start_polling(bot))
        await polling_task
        
    except Exception as e:
        logger.exception(f"Fatal error during polling: {e}")
    finally:
        logger.info("Starting graceful shutdown...")
        
        # Остановка планировщика
        try:
            if scheduler.running:
                scheduler.shutdown(wait=False)
                logger.info("Scheduler stopped")
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}")
        
        # Остановка polling
        if polling_task and not polling_task.done():
            polling_task.cancel()
            try:
                await asyncio.wait_for(polling_task, timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                logger.info("Polling task cancelled")
        
        # Закрытие базы данных
        try:
            from app.utils.database import close_database_connections
            await close_database_connections()
        except Exception as e:
            logger.error(f"Error closing database connections: {e}")
        
        # Закрытие сессии бота
        if bot:
            try:
                await bot.session.close()
                logger.info("Bot session closed")
            except Exception as e:
                logger.error(f"Error closing bot session: {e}")

        if client_session and not client_session.closed:
            try:
                # Даем время на завершение всех запросов
                await asyncio.sleep(0.5)
                await client_session.close()
                logger.info("Aiohttp client session closed")
            except Exception as e:
                logger.error(f"Error closing aiohttp client session: {e}")
                
        try:
            # Принудительное закрытие всех соединений через garbage collector
            import gc
            import aiohttp
            
            for obj in gc.get_objects():
                if isinstance(obj, aiohttp.TCPConnector):
                    try:
                        await obj.close()
                        logger.debug("TCPConnector closed via GC")
                    except:
                        pass
        except Exception as e:
            logger.error(f"Error during final cleanup: {e}")
        
        logger.info("Shutdown complete")
from aiogram import Router

router = Router()

from .subscription import router as subscription_router
from .gdz import router as gdz_router
from .books import router as books_router
from .settings import router as settings_router

router.include_routers(subscription_router, gdz_router, books_router, settings_router)
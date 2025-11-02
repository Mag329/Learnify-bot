from aiogram import Router

router = Router()

from .subscription import router as subscription_router
from .gdz import router as gdz_router

router.include_routers(subscription_router, gdz_router)
# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram import Router

router = Router()

from .books import router as books_router
from .gdz import router as gdz_router
from .settings import router as settings_router
from .subscription import router as subscription_router

router.include_routers(subscription_router, gdz_router, books_router, settings_router)

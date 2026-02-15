# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

scheduler = AsyncIOScheduler(timezone=timezone("Europe/Moscow"))

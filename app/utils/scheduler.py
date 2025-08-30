from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

# создаём единый scheduler для всего проекта
scheduler = AsyncIOScheduler(timezone=timezone("Europe/Moscow"))

import os

import yaml

import app.keyboards.user.keyboards as kb
from app.config.config import (CHANNEL_ID, DEFAULT_MEDIUM_CACHE_TTL,
                               NO_SUBSCRIPTION_ERROR)
from app.utils.database import AsyncSessionLocal, SettingDefinition, db
from app.utils.user.cache import redis_client
from app.utils.user.utils import user_send_message


async def create_settings_definitions_if_not_exists():
    async with AsyncSessionLocal() as session:
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "initial_settings.yaml"
        )
        with open(path, encoding="utf-8") as f:
            settings = yaml.safe_load(f)

        for setting in settings:
            exists = await session.scalar(
                db.select(SettingDefinition).where(
                    SettingDefinition.key == setting["key"]
                )
            )
            if not exists:
                session.add(SettingDefinition(**setting))

        await session.commit()


async def check_subscription(user_id, bot):
    if not CHANNEL_ID:
        return True

    cache_key = f"subscriptions:{user_id}"
    cache = await redis_client.get(cache_key)
    if cache:
        return cache == "true"

    user_channel_status = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
    if user_channel_status.status != "left":
        await redis_client.setex(cache_key, DEFAULT_MEDIUM_CACHE_TTL, "true")

        return True
    else:
        return False

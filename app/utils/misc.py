import os
import re
import yaml
from aiogram.fsm.context import FSMContext
from transliterate import translit

import app.keyboards.user.keyboards as kb
from app.config.config import (CHANNEL_ID, DEFAULT_MEDIUM_CACHE_TTL,
                               NO_SUBSCRIPTION_TO_CHANNEL_ERROR)
from app.states.user.states import QuickGdzState
from app.utils.database import (AsyncSessionLocal, PremiumSubscriptionPlan,
                                SettingDefinition, db)
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
        

async def create_premium_subscription_plans_if_not_exists():
    async with AsyncSessionLocal() as session:
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "premium_plans.yaml"
        )
        with open(path, encoding="utf-8") as f:
            plans = yaml.safe_load(f)

        for plan in plans:
            exists = await session.scalar(
                db.select(PremiumSubscriptionPlan).where(
                    PremiumSubscriptionPlan.name == plan["name"]
                )
            )
            if not exists:
                session.add(PremiumSubscriptionPlan(**plan))

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


async def has_numbers(text):
    return bool(re.search(r'\d', text))


async def clear_state_if_still_waiting(state: FSMContext):
    current_state = await state.get_state()
    if current_state == QuickGdzState.number:
        await state.clear()
        
        
def sanitize_filename(name: str) -> str:
    """Очистка и нормализация имени файла"""
    # Транслитерация русских букв → латиница
    name = translit(name, 'ru', reversed=True)
    # Пробелы → дефисы
    name = re.sub(r"\s+", "-", name.strip())
    # Убираем всё, кроме букв, цифр и дефисов
    name = re.sub(r"[^a-zA-Z0-9\-]", "", name)
    return name.lower()
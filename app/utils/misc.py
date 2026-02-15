import os
import re

import yaml
from aiogram.fsm.context import FSMContext
from loguru import logger
from transliterate import translit

from app.config.config import (
    CHANNEL_ID,
    DEFAULT_MEDIUM_CACHE_TTL,
)
from app.states.user.states import QuickGdzState
from app.utils.database import (
    get_session,
    PremiumSubscriptionPlan,
    SettingDefinition,
    db,
)
from app.utils.user.cache import redis_client


async def create_settings_definitions_if_not_exists():
    logger.info("Creating settings definitions if not exists...")
    async with await get_session() as session:
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "initial_settings.yaml"
        )
        logger.debug(f"Loading settings from: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                settings = yaml.safe_load(f)
            logger.debug(f"Loaded {len(settings)} settings definitions")
        except FileNotFoundError:
            logger.error(f"Settings file not found: {path}")
            return
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {path}: {e}")
            return

        created_count = 0
        for setting in settings:
            exists = await session.scalar(
                db.select(SettingDefinition).where(
                    SettingDefinition.key == setting["key"]
                )
            )
            if not exists:
                session.add(SettingDefinition(**setting))
                created_count += 1
                logger.debug(f"Added setting: {setting['key']}")

        await session.commit()
        logger.info(
            f"Settings definitions created/verified. Created: {created_count}, Total: {len(settings)}"
        )


async def create_premium_subscription_plans_if_not_exists():
    logger.info("Creating premium subscription plans if not exists...")
    async with await get_session() as session:
        path = os.path.join(
            os.path.dirname(__file__), "..", "config", "premium_plans.yaml"
        )
        logger.debug(f"Loading premium plans from: {path}")

        try:
            with open(path, encoding="utf-8") as f:
                plans = yaml.safe_load(f)
            logger.debug(f"Loaded {len(plans)} premium plans")
        except FileNotFoundError:
            logger.error(f"Premium plans file not found: {path}")
            return
        except yaml.YAMLError as e:
            logger.error(f"Error parsing YAML file {path}: {e}")
            return

        created_count = 0
        for plan in plans:
            exists = await session.scalar(
                db.select(PremiumSubscriptionPlan).where(
                    PremiumSubscriptionPlan.name == plan["name"]
                )
            )
            if not exists:
                session.add(PremiumSubscriptionPlan(**plan))
                created_count += 1
                logger.debug(f"Added premium plan: {plan['name']}")

        await session.commit()
        logger.info(
            f"Premium plans created/verified. Created: {created_count}, Total: {len(plans)}"
        )


async def check_subscription(user_id, bot):
    if not CHANNEL_ID:
        logger.debug(
            f"Channel ID not configured, subscription check skipped for user {user_id}"
        )
        return True

    cache_key = f"subscriptions:{user_id}"

    # Check cache
    cache = await redis_client.get(cache_key)
    if cache:
        is_subscribed = cache == "true"
        logger.debug(f"Subscription cache hit for user {user_id}: {is_subscribed}")
        return is_subscribed

    logger.debug(f"Checking subscription for user {user_id} in channel {CHANNEL_ID}")
    try:
        user_channel_status = await bot.get_chat_member(
            chat_id=CHANNEL_ID, user_id=user_id
        )
        is_subscribed = user_channel_status.status != "left"

        if is_subscribed:
            await redis_client.setex(cache_key, DEFAULT_MEDIUM_CACHE_TTL, "true")
            logger.debug(
                f"User {user_id} is subscribed, cached for {DEFAULT_MEDIUM_CACHE_TTL} seconds"
            )
        else:
            logger.debug(f"User {user_id} is not subscribed to channel")

        return is_subscribed
    except Exception as e:
        logger.error(f"Error checking subscription for user {user_id}: {e}")
        return True


async def has_numbers(text):
    result = bool(re.search(r"\d", text))
    logger.debug(f"Checking if text '{text[:50]}...' contains numbers: {result}")
    return result


async def clear_state_if_still_waiting(state: FSMContext):
    current_state = await state.get_state()
    if current_state == QuickGdzState.number:
        logger.debug(f"Clearing state {current_state} (still waiting)")
        await state.clear()
    else:
        logger.debug(f"State {current_state} not cleared (not in waiting state)")


def sanitize_filename(name: str) -> str:
    logger.debug(f"Sanitizing filename: {name}")

    name = translit(name, "ru", reversed=True)
    logger.debug(f"After transliteration: {name}")

    name = re.sub(r"\s+", "-", name.strip())
    logger.debug(f"After space replacement: {name}")

    original_length = len(name)
    name = re.sub(r"[^a-zA-Z0-9\-]", "", name)
    if len(name) != original_length:
        logger.debug(f"Removed {original_length - len(name)} invalid characters")

    result = name.lower()
    logger.debug(f"Final sanitized filename: {result}")
    return result

# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import asyncio
import uuid
from datetime import datetime, timedelta
from io import BytesIO

import jwt
from aiogram import Bot
from aiogram.types import BufferedInputFile
from loguru import logger

from app.keyboards import user as kb
from app.config.config import LEARNIFY_WEB
from app.utils.database import get_session, AuthData, User, db
from app.utils.scheduler import scheduler
from app.utils.user.utils import get_student


async def decode_token(token):
    logger.debug(f"Decoding JWT token")
    try:
        decoded = jwt.decode(token, options={"verify_signature": False})
        logger.debug(f"Token decoded successfully, exp: {decoded.get('exp')}")
        return decoded
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return {}


async def get_token_expire_date(token, hours_shift=16):
    logger.debug(f"Getting token expire date with {hours_shift}h shift")
    data = await decode_token(token)

    if not data or "exp" not in data:
        logger.warning("Token has no expiration field")
        return datetime.now() + timedelta(days=30)  # Fallback

    expire_dt = datetime.fromtimestamp(data["exp"])
    result = expire_dt - timedelta(hours=hours_shift)
    logger.debug(f"Token expires at {expire_dt}, refresh scheduled at {result}")
    return result


async def get_login_qr_code(session):
    logger.info("Generating login QR code")
    
    params = {
        "scope": "birthday contacts openid profile snils blitz_change_password blitz_user_rights blitz_qr_auth",
        "access_type": "offline",
        "response_type": "code",
        "state": str(uuid.uuid4()),
        "client_id": "dnevnik.mos.ru",
        "redirect_uri": "https://school.mos.ru/v3/auth/sudir/callback",
        "display": "script",
        "code_challenge_method": "S256",
    }
    
    logger.debug("Requesting QR code data from login.mos.ru")
    async with session.get(
        "https://login.mos.ru/sps/oauth/ae", params=params
    ) as response:
        data = await response.json()
        logger.debug(f"Response status: {response.status}")

    try:
        qr_code = next(item for item in data["items"] if item["inquire"] == "show_qr_code")
        logger.debug("QR code data found in response")
    except StopIteration:
        logger.error("No QR code data in response")
        return False, None

    url = f"{LEARNIFY_WEB}/api/v1/utils/qr"
    payload = {"data": qr_code["link"]}
    
    logger.debug(f"Sending QR generation request to {url}")
    async with session.post(url, json=payload) as response:
        if response.status == 200:
            image_bytes = await response.read()
            logger.info(f"QR code generated successfully, size: {len(image_bytes)} bytes")

            file = BytesIO(image_bytes)
            file.name = "qr_code.png"  # Telegram требует имя файла

            return True, BufferedInputFile(file.read(), filename="qr_code.png")
        else:
            logger.error(f"Failed to generate QR code, status: {response.status}")
            return False, None


async def check_qr_login(session):
    logger.info("Checking QR login status")
    elapsed = 0

    while elapsed <= 300:
        timestamp = int(round(datetime.now().timestamp() * 1000))
        logger.debug(f"Polling QR login status, elapsed: {elapsed}s")
        
        async with session.get(
            f"https://login.mos.ru/sps/login/methods/qrCode/pull?_={timestamp}"
        ) as response:
            data = await response.json()
        command = data["command"]
        logger.debug(f"Received command: {command}")
        
        if command == "needComplete":
            logger.info("QR login ready to complete")
            break
        
        delay = 5
        await asyncio.sleep(delay)
        elapsed += delay

    logger.debug("Completing QR login")
    async with session.post(
        "https://login.mos.ru/sps/login/methods/headless/qrCode/complete"
    ) as response:
        if response.status == 200:
            for cookie in response.cookies.values():
                if cookie.key == "aupd_token":
                    logger.info("QR login successful, aupd_token obtained")
                    return cookie.value

        logger.error(f"QR login completion failed, status: {response.status}")
        return None


async def refresh_token(user_id, bot: Bot):
    async with await get_session() as session:
        logger.info(f"Refreshing token for user {user_id}")
        
        result = await session.execute(
            db.select(User).filter_by(user_id=user_id, active=True)
        )
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"User {user_id} not found or inactive, cannot refresh token")
            return

        api, _ = await get_student(user_id)

        result = await session.execute(
            db.select(AuthData).filter_by(user_id=user_id, auth_method="password")
        )
        auth_data: AuthData = result.scalar_one_or_none()

        if not auth_data:
            logger.warning(f"No auth data found for user {user_id}")
            return
        
        try:
            logger.debug(f"Attempting to refresh token for user {user_id}")
            token = await api.refresh_token(
                auth_data.token_for_refresh,
                auth_data.client_id,
                auth_data.client_secret,
            )
            if token:
                user.token = token
                auth_data.token_for_refresh = api.token_for_refresh
                need_update_date = await get_token_expire_date(api.token)
                auth_data.token_expired_at = need_update_date
                await session.commit()
                
                logger.success(f"Token refreshed successfully for user {user_id}, new expiry: {need_update_date}")

                await schedule_refresh(user.user_id, need_update_date, bot)
            else:
                logger.error(f"Token refresh returned None for user {user_id}")
                
        except Exception as e:
            logger.error(f"Error refreshing token for user {user_id}: {e}")

            try:
                chat = await bot.get_chat(user.user_id)
                await bot.send_message(
                    chat_id=chat.id,
                    text=f"❌ <b>Произошла ошибка при обновление токена доступа МЭШ</b>\nПожалуйста попробуйте авторизоваться заново",
                    reply_markup=kb.delete_message,
                )
                logger.info(f"Sent error notification to user {user_id}")
            except Exception as e2:
                logger.error(f"Failed to send error notification to user {user_id}: {e2}")


async def schedule_refresh(user_id: int, expires_at: datetime, bot: Bot, need_update=False):
    job_id = f"refresh_token_{user_id}"
    logger.info(f"Scheduling token refresh for user {user_id} at {expires_at}, job_id: {job_id}")

    if expires_at < datetime.now() or need_update:
        await refresh_token(user_id, bot)
    else:
        scheduler.add_job(
            refresh_token,
            "date",
            run_date=expires_at,
            args=[user_id, bot],
            id=job_id,
            replace_existing=True,
        )
        logger.debug(f"Refresh job scheduled for user {user_id}")


def delete_refresh_task(user_id):
    job_id = f"refresh_token_{user_id}"
    logger.info(f"Deleting refresh task for user {user_id}, job_id: {job_id}")

    try:
        scheduler.remove_job(job_id)
        logger.debug(f"Refresh task deleted for user {user_id}")
    except Exception as e:
        logger.debug(f"No refresh task found for user {user_id} to delete: {e}")


async def restore_refresh_tokens_jobs(bot):
    logger.info("Restoring scheduled token refresh jobs")
    
    async with await get_session() as session:
        result = await session.execute(
            db.select(AuthData).filter_by(auth_method="password")
        )
        tokens = result.scalars().all()
        logger.info(f"Found {len(tokens)} users with password auth to restore")
        
        restored_count = 0
        for token in tokens:
            try:
                await schedule_refresh(token.user_id, token.token_expired_at, bot)
                restored_count += 1
                logger.debug(f"Restored refresh job for user {token.user_id}")
            except Exception as e:
                logger.error(f"Failed to restore refresh job for user {token.user_id}: {e}")
        
        logger.success(f"Restored {restored_count}/{len(tokens)} refresh jobs")

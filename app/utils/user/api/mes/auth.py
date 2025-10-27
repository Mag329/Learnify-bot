import asyncio
import uuid
from datetime import datetime, timedelta
from io import BytesIO
import logging

from aiogram import Bot
import aiohttp
import jwt
import pytz
from aiogram.types import BufferedInputFile

from app.config.config import LEARNIFY_WEB
from app.utils.database import AsyncSessionLocal, AuthData, User, db
from app.utils.scheduler import scheduler
from app.utils.user.utils import get_student
import app.keyboards.user.keyboards as kb


logger = logging.getLogger(__name__)


async def decode_token(token):
    return jwt.decode(token, options={"verify_signature": False})


async def get_token_expire_date(token, hours_shift=16):
    data = await decode_token(token)

    expire_dt = datetime.fromtimestamp(data["exp"])
    return expire_dt - timedelta(hours=hours_shift)


async def get_login_qr_code(session):
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
    headers = {"Content-Type": "application/json"}
    async with session.get(
        "https://login.mos.ru/sps/oauth/ae", params=params, headers=headers
    ) as response:
        data = await response.json()

    qr_code = next(item for item in data["items"] if item["inquire"] == "show_qr_code")

    url = f"{LEARNIFY_WEB}/api/v1/generate/qr"
    payload = {"data": qr_code["link"]}

    async with session.post(url, json=payload) as response:
        if response.status == 200:
            image_bytes = await response.read()

            file = BytesIO(image_bytes)
            file.name = "qr_code.png"  # Telegram требует имя файла

            return True, BufferedInputFile(file.read(), filename="qr_code.png")
        else:
            return False, None


async def check_qr_login(session):
    elapsed = 0

    while elapsed <= 300:
        timestamp = int(round(datetime.now().timestamp() * 1000))
        async with session.get(
            f"https://login.mos.ru/sps/login/methods/qrCode/pull?_={timestamp}"
        ) as response:
            data = await response.json()
        command = data["command"]
        if command == "needComplete":
            break
        delay = 5
        await asyncio.sleep(delay)
        elapsed += delay

    async with session.post(
        "https://login.mos.ru/sps/login/methods/headless/qrCode/complete"
    ) as response:
        if response.status == 200:
            for cookie in response.cookies.values():
                if cookie.key == "aupd_token":
                    return cookie.value

        return None


async def refresh_token(user_id, bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(User).filter_by(user_id=user_id, active=True)
        )
        user = result.scalar_one_or_none()

        api, _ = await get_student(user_id)

        result = await session.execute(
            db.select(AuthData).filter_by(user_id=user_id, auth_method="password")
        )
        auth_data: AuthData = result.scalar_one_or_none()
        
        
        try:
            if auth_data:
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

                    schedule_refresh(user.user_id, need_update_date, bot)
        except Exception as e:
            logger.error(f'Error refreshing token for user {user.user_id}: {e}')
            
            try:
                chat = await bot.get_chat(user.user_id)
                await bot.send_message(
                    chat_id=chat.id,
                    text=f"❌ <b>Произошла ошибка при обновление токена доступа МЭШ</b>\nПожалуйста попробуйте авторизоваться заново",
                    reply_markup=kb.delete_message,
                )
            except Exception as e:
                pass



def schedule_refresh(user_id: int, expires_at: datetime, bot: Bot):
    job_id = f"refresh_token_{user_id}"

    if expires_at < datetime.now():
        refresh_token(user_id, bot)
    else:
        scheduler.add_job(
            refresh_token,
            "date",
            run_date=expires_at,
            args=[user_id, bot],
            id=job_id,
            replace_existing=True,
        )


def delete_refresh_task(user_id):
    job_id = f"refresh_token_{user_id}"

    try:
        scheduler.remove_job(job_id)
    except:
        pass


async def restore_refresh_tokens_jobs(bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(AuthData).filter_by(auth_method="password")
        )
        tokens = result.scalars().all()
        for token in tokens:
            schedule_refresh(token.user_id, token.token_expired_at, bot)

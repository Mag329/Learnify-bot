import aiohttp
from io import BytesIO
from aiogram.types import BufferedInputFile
import uuid
import jwt
from datetime import datetime, timedelta
import asyncio

from app.config.config import LEARNIFY_WEB


async def decode_token(token):
    return jwt.decode(token, options={"verify_signature": False})


async def get_token_expire_date(token, hours_shift=16):
    data = await decode_token(token)

    expire_dt = datetime.fromtimestamp(data['exp'])
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
    headers = {
        'Content-Type': 'application/json'
    }
    async with session.get("https://login.mos.ru/sps/oauth/ae", params=params, headers=headers) as response:
        data = await response.json()

    qr_code = next(item for item in data["items"] if item["inquire"] == "show_qr_code")
        
    url = f'{LEARNIFY_WEB}/api/v1/generate/qr'
    payload = {'data': qr_code["link"]}

    async with session.post(url, json=payload) as response:
        if response.status == 200:
            image_bytes = await response.read()

            file = BytesIO(image_bytes)
            file.name = 'qr_code.png'  # Telegram требует имя файла

            return True, BufferedInputFile(file.read(), filename="qr_code.png")
        else:
            return False, None
            
            
async def check_qr_login(session):
    elapsed = 0
    
    while elapsed <= 300:
        timestamp = int(round(datetime.now().timestamp() * 1000))
        async with session.get(f"https://login.mos.ru/sps/login/methods/qrCode/pull?_={timestamp}") as response:
            data = await response.json()
        command = data["command"]
        if command == "needComplete":
            break
        delay = 5
        await asyncio.sleep(delay)
        elapsed += delay
        
    async with session.post("https://login.mos.ru/sps/login/methods/headless/qrCode/complete") as response:
        if response.status == 200:
            for cookie in response.cookies.values():
                if cookie.key == "aupd_token":
                    return cookie.value
            
        return None
        
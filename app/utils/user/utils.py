import random
from datetime import datetime, timedelta, timezone

import phonenumbers
from aiogram.types import Message
from octodiary.apis import AsyncMobileAPI, AsyncWebAPI
from octodiary.exceptions import APIError
from octodiary.urls import Systems

import app.keyboards.user.keyboards as kb
from app.config.config import (ERROR_403_MESSAGE, ERROR_408_MESSAGE,
                               ERROR_500_MESSAGE, ERROR_MESSAGE)
from app.utils.database import (AsyncSessionLocal, Event, SettingDefinition,
                                Settings, User, UserData, db)
from app.utils.user.decorators import handle_api_error

EMOJI_SUBJECTS = {
    "Иностранный (английский) язык": "🇬🇧",
    "Алгебра": "➗",
    "Вероятность и статистика": "📊",
    "Геометрия": "📐",
    "Информатика": "💻",
    "Математика": "🧮",
    "Литература": "📚",
    "Русский язык": "🇷🇺",
    "Практикум по русскому языку": "📝",
    "Основы безопасности и защиты Родины": "🛡️",
    "Биология": "🧬",
    "Физика": "🔬",
    "Химия": "⚗️",
    "Физическая культура": "🏋️",
    "География": "🗺️",
    "История": "🏺",
    "Обществознание": "⚖️",
    "Труд (технология)": "🔧",
}

EMOJI_OTHER_SUBJECTS = ["📒", "📕", "📗", "📘", "📙"]

EMOJI_NUMBERS = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}

SUBSCRIPT_MAP = str.maketrans("12345", "₁₂₃₄₅")


async def user_send_message(user_id, message, markup=None):
    from app import bot

    try:
        chat = await bot.get_chat(user_id)
        if markup:
            await bot.send_message(chat_id=chat.id, text=message, reply_markup=markup)
        else:
            await bot.send_message(chat_id=chat.id, text=message)
    except Exception as e:
        return


async def get_emoji_subject(name):
    return EMOJI_SUBJECTS.get(name, random.choice(EMOJI_OTHER_SUBJECTS))


async def get_mark_with_weight(mark, weight):
    return f"{mark}{str(weight).translate(SUBSCRIPT_MAP)}"


@handle_api_error()
async def get_student(user_id, active=True):
    async with AsyncSessionLocal() as session:
        query = db.select(User).filter_by(user_id=user_id)
        if active:
            query = query.filter_by(active=True)

        result = await session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return None, None

        api = AsyncMobileAPI(system=Systems.MES)
        api.token = user.token
        return api, user


@handle_api_error()
async def get_web_api(user_id, active=True):
    async with AsyncSessionLocal() as session:
        query = db.select(User).filter_by(user_id=user_id)
        if active:
            query = query.filter_by(active=True)

        result = await session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return None, None

        api = AsyncWebAPI(system=Systems.MES)
        api.token = user.token
        return api, user


async def render_settings_text(definitions, settings, selected_key):
    lines = []
    for definition in definitions:
        val = getattr(settings, definition.key, None)
        display = "✅" if val is True else "❌" if val is False else str(val)
        prefix = "➡️" if definition.key == selected_key else "▫️"
        lines.append(f"{prefix} {definition.label}: {display}")
    return "\n\n".join(lines)


async def send_settings_editor(message_or_callback, selected_index: int):
    async with AsyncSessionLocal() as session:
        user_id = message_or_callback.from_user.id
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings = result.scalars().first()

        result = await session.execute(
            db.select(SettingDefinition)
            .filter_by(visible=True)
            .order_by(SettingDefinition.ordering)
        )
        definitions = result.scalars().all()

        selected_index = max(0, min(selected_index, len(definitions) - 1))
        selected_key = definitions[selected_index].key

        text = "⚙️ <b>Настройки</b>\n\n"
        text += await render_settings_text(definitions, settings, selected_key)
        keyboard = await kb.build_settings_nav_keyboard(definitions, selected_index)

        if isinstance(message_or_callback, Message):
            await message_or_callback.answer(text, reply_markup=keyboard)
        else:
            await message_or_callback.message.edit_text(text, reply_markup=keyboard)


def get_error_message_by_status(status_code: int) -> str:
    if status_code == 408:
        return ERROR_408_MESSAGE
    elif status_code in [500, 501, 502]:
        return ERROR_500_MESSAGE
    else:
        return ERROR_MESSAGE


async def ensure_user_settings(session, user_id: int):
    result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
    settings = result.scalar_one_or_none()
    if not settings:
        session.add(Settings(user_id=user_id))
        await session.commit()


async def save_profile_data(session, user_id, profile_data):
    result = await session.execute(db.select(UserData).filter_by(user_id=user_id))
    user_data = result.scalar_one_or_none()

    web_api, _ = await get_web_api(user_id)
    web_profile = await web_api.get_user_info()

    if not user_data:
        user_data = UserData(
            user_id=user_id,
            first_name=profile_data.first_name,
            last_name=profile_data.last_name,
            middle_name=profile_data.middle_name,
            gender=profile_data.sex,
            phone=web_profile.info.mobile,
            email=web_profile.info.mail,
            birthday=profile_data.birth_date,
        )
        session.add(user_data)

    await session.commit()


async def parse_and_format_phone(raw_number: str) -> str:
    try:
        raw_number = raw_number.strip()

        # Преобразуем "8" в "+7" (только если длина 11 и начинается с "8")
        if raw_number.startswith("8") and len(raw_number) == 11:
            raw_number = "+7" + raw_number[1:]

        # Если просто начинается с "7" и длина 11, добавляем "+"
        elif raw_number.startswith("7") and len(raw_number) == 11:
            raw_number = "+" + raw_number

        # Если начинается с "00" (международный формат), заменим на "+"
        elif raw_number.startswith("00"):
            raw_number = "+" + raw_number[2:]

        # Парсим номер (без указания региона — универсально)
        phone = phonenumbers.parse(raw_number, None)

        if not phonenumbers.is_valid_number(phone):
            return "Неверный номер"

        return phonenumbers.format_number(
            phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )

    except phonenumbers.NumberParseException:
        return "Н/Д"

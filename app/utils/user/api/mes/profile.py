# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from datetime import datetime
from loguru import logger

from app.config.config import DEFAULT_LONG_CACHE_TTL
from app.utils.database import get_session, UserData, db
from app.utils.user.decorators import cache_text_only, handle_api_error
from app.utils.user.utils import get_student, parse_and_format_phone


@handle_api_error()
@cache_text_only(DEFAULT_LONG_CACHE_TTL)
async def get_profile(user_id):
    logger.info(f"Getting profile for user {user_id}")
    
    logger.debug(f"Fetching student data for user {user_id}")
    api, user = await get_student(user_id)
    if not api or not user:
        logger.error(f"Failed to get student data for user {user_id}")
        return "❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика"
    
    logger.debug(f"Fetching family profile for user {user_id}")
    profile = await api.get_family_profile(profile_id=user.profile_id)
    data = profile.profile

    logger.debug(f"Fetching user data from database for user {user_id}")
    async with await get_session() as session:
        result = await session.execute(db.select(UserData).filter_by(user_id=user_id))
        user_data: UserData = result.scalar_one_or_none()

    # Баланс
    logger.debug(f"Fetching balance for user {user_id}")
    balance_data = await api.get_status(
        profile_id=user.profile_id, contract_ids=user.contract_id
    )
    
    if balance_data and balance_data.students:
        balance = balance_data.students[0].balance / 100
        logger.debug(f"User balance: {balance} ₽")
    else:
        balance = "Н/Д"
        logger.warning(f"No balance data available for user {user_id}")

    # Форматирование телефона
    formatted_phone = "Н/Д"
    if user_data and user_data.phone:
        formatted_phone = await parse_and_format_phone(user_data.phone)
        logger.debug(f"Formatted phone: {formatted_phone}")
    else:
        logger.debug(f"No phone data for user {user_id}")
    
    email = user_data.email if user_data.email else "Н/Д"

    # Расчет возраста
    current_date = datetime.today()
    age = current_date.year - data.birth_date.year
    if (current_date.month, current_date.day) < (
        data.birth_date.month,
        data.birth_date.day,
    ):
        age -= 1
    logger.debug(f"User age: {age} years")

    # Поиск информации о школе и классе
    school_info = None
    class_name = None
    classroom_teacher_name = None
    
    for children in profile.children:
        if (
            children.last_name == data.last_name
            and children.first_name == data.first_name
            and children.middle_name == data.middle_name
        ):
            school = children.school
            logger.debug(f"Found school: {school.short_name}")
            
            school_info = await api.get_school_info(
                profile_id=user.profile_id,
                school_id=school.id,
                class_unit_id=children.class_unit_id,
            )
            class_name = children.class_name
            logger.debug(f"Class: {class_name}")
            break

    if school_info and school_info.classroom_teachers:
        classroom_teacher = school_info.classroom_teachers[0]
        classroom_teacher_name = f"{classroom_teacher.last_name} {classroom_teacher.first_name} {classroom_teacher.middle_name}"
        logger.debug(f"Classroom teacher: {classroom_teacher_name}")
    else:
        classroom_teacher_name = "Н/Д"
        logger.warning(f"No classroom teacher data for user {user_id}")

    # Формирование текста профиля
    text = "👤 <b>Профиль</b>\n\n"
    text += f"🆔 <b>ID:</b> <code>{data.id}</code>\n"
    text += f"📝 <b>Имя:</b> <code>{data.first_name}</code>\n"
    text += f"📜 <b>Фамилия:</b> <code>{data.last_name}</code>\n"
    text += f"🧬 <b>Отчество:</b> <code>{data.middle_name}</code>\n\n"

    text += f"✉️ <b>Почта:</b> <code>{email}</code>\n"
    text += f"📱 <b>Телефон:</b> <code>{formatted_phone}</code>\n"
    
        # Форматирование СНИЛС
    if hasattr(data, 'snils') and data.snils:
        snils = data.snils
        if len(snils) >= 11:
            formatted_snils = f"{snils[:3]}-{snils[3:6]}-{snils[6:9]}-{snils[9:]}"
        else:
            formatted_snils = snils
    else:
        formatted_snils = "Н/Д"
    
    text += f"🪪 <b>СНИЛС:</b> <code>{formatted_snils}</code>\n\n"

    text += f"💰 <b>Баланс:</b> <code>{balance} ₽</code>\n\n"

    text += f"🎂 <b>Дата рождения:</b> <code>{data.birth_date.strftime('%d %B %Y')}</code>\n"
    text += f"🔢 <b>Возраст:</b> <code>{age}</code>\n\n"

    text += f"🏫 <b>Школа:</b> <code>{school.short_name}</code>\n"
    text += f"🧑‍💼 <b>Директор:</b> <code>{school.principal}</code>\n"
    text += f"📚 <b>Класс:</b> <code>{class_name}</code>\n"
    text += (
        f"👩‍🏫 <b>Классный руководитель:</b> <code>{classroom_teacher_name}</code>\n"
    )

    logger.success(f"Profile generated successfully for user {user_id}")
    return text
from datetime import datetime

from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import (get_student, get_web_api,
                                  parse_and_format_phone)


@handle_api_error()
async def get_profile(user_id):
    api, user = await get_student(user_id)
    web_api, _ = await get_web_api(user_id)
    profile = await api.get_family_profile(profile_id=user.profile_id)
    data = profile.profile
    web_profile = await web_api.get_user_info()

    # Баланс
    balance_data = await api.get_status(
        profile_id=user.profile_id, contract_ids=user.contract_id
    )
    balance = balance_data.students[0].balance / 100 if balance_data.students else "Н/Д"

    formatted_phone = await parse_and_format_phone(web_profile.info.mobile)

    current_date = datetime.today()
    age = current_date.year - data.birth_date.year
    if (current_date.month, current_date.day) < (
        data.birth_date.month,
        data.birth_date.day,
    ):
        age -= 1

    for children in profile.children:
        if (
            children.last_name == data.last_name
            and children.first_name == data.first_name
            and children.middle_name == data.middle_name
        ):
            school = children.school
            class_name = children.class_name

    text = "👤 <b>Профиль</b>\n\n"
    text += f"🆔 <b>ID:</b> <code>{data.id}</code>\n"
    text += f"📝 <b>Имя:</b> <code>{data.first_name}</code>\n"
    text += f"📜 <b>Фамилия:</b> <code>{data.last_name}</code>\n"
    text += f"🧬 <b>Отчество:</b> <code>{data.middle_name}</code>\n\n"

    text += f"✉️ <b>Почта:</b> <code>{data.email}</code>\n"
    text += f"📱 <b>Телефон:</b> <code>{formatted_phone}</code>\n"
    text += f"🪪 <b>СНИЛС:</b> <code>{data.snils[:3]}-{data.snils[3:6]}-{data.snils[6:9]}-{data.snils[9:]}</code>\n\n"

    text += f"💰 <b>Баланс:</b> <code>{balance} ₽</code>\n\n"

    text += f"🎂 <b>Дата рождения:</b> <code>{data.birth_date.strftime('%d %B %Y')}</code>\n"
    text += f"🔢 <b>Возраст:</b> <code>{age}</code>\n\n"

    text += f"🏫 <b>Школа:</b> <code>{school.short_name}</code>\n"
    text += f"🧑‍💼 <b>Директор:</b> <code>{school.principal}</code>\n"
    text += f"📚 <b>Класс:</b> <code>{class_name}</code>\n\n"

    return text

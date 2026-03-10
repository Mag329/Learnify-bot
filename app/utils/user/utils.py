# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import random
from datetime import datetime

import phonenumbers
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.media_group import MediaGroupBuilder
from loguru import logger
from octodiary.apis import AsyncMobileAPI, AsyncWebAPI
from octodiary.urls import Systems

from app.keyboards import user as kb
from app.config import config
from app.config.config import (
    ERROR_408_MESSAGE,
    ERROR_500_MESSAGE,
    ERROR_MESSAGE,
    NO_PREMIUM_ERROR,
)
from app.utils.database import (
    get_session,
    Gdz,
    Homework,
    PremiumSubscription,
    SettingDefinition,
    Settings,
    User,
    UserData,
    db,
)
from app.utils.user.decorators import handle_api_error

EMOJI_SUBJECTS = {
    "Иностранный (английский) язык": "🇬🇧",
    "Алгебра": "➗",
    "Алгебра и начала математического анализа": "➗",
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
    "Индивидуальный проект": "📑",
    "Экономика": "💰",
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
    from app import bot_instance as bot

    try:
        chat = await bot.get_chat(user_id)
        if markup:
            await bot.send_message(chat_id=chat.id, text=message, reply_markup=markup)
        else:
            await bot.send_message(chat_id=chat.id, text=message)
        logger.debug(f"Message sent to user {user_id}")
    except Exception as e:
        logger.error(f"Failed to send message to user {user_id}: {e}")
        return


async def get_emoji_subject(name):
    return EMOJI_SUBJECTS.get(name, random.choice(EMOJI_OTHER_SUBJECTS))


async def get_mark_with_weight(mark, weight):
    return f"{mark}{str(weight).translate(SUBSCRIPT_MAP)}"


@handle_api_error()
async def get_student(user_id, active=True) -> list[AsyncMobileAPI, User]:
    logger.debug(f"Getting student data for user {user_id}, active={active}")

    async with await get_session() as session:
        try:
            query = db.select(User).filter_by(user_id=user_id)
            if active:
                query = query.filter_by(active=True)

            result = await session.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {user_id} not found or inactive")
                return None, None

            api = AsyncMobileAPI(system=Systems.MES)
            api.token = user.token
            logger.debug(f"Student API created for user {user_id}")
            return api, user
        except Exception as e:
            logger.exception(f"Error getting student data for user {user_id}: {e}")
            return None, None


@handle_api_error()
async def get_web_api(user_id, active=True) -> list[AsyncWebAPI, User]:
    logger.debug(f"Getting web API for user {user_id}, active={active}")

    async with await get_session() as session:
        try:
            query = db.select(User).filter_by(user_id=user_id)
            if active:
                query = query.filter_by(active=True)

            result = await session.execute(query)
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"User {user_id} not found or inactive")
                return None, None

            api = AsyncWebAPI(system=Systems.MES)
            api.token = user.token
            return api, user
        except Exception as e:
            logger.exception(f"Error getting web API for user {user_id}: {e}")
            return None, None


async def render_settings_text(
    definitions, settings, selected_key, is_experimental=False
):
    logger.debug(
        f"Rendering settings text, selected_key={selected_key}, is_experimental={is_experimental}"
    )

    lines = []
    for definition in definitions:
        # Пропускаем невидимые настройки
        if not definition.visible:
            continue

        val = getattr(settings, definition.key, None)
        display = "✅" if val is True else "❌" if val is False else str(val)
        prefix = "➡️" if definition.key == selected_key else "▫️"

        # Добавляем эмодзи для экспериментальных функций
        if definition.experimental:
            display = f"{display}"

        lines.append(f"{prefix} {definition.label}: {display}")

    result = "\n\n".join(lines)
    logger.debug(f"Settings text rendered, {len(lines)} lines")
    return result


async def send_settings_editor(
    message_or_callback, selected_index: int, is_experimental=False
):
    user_id = message_or_callback.from_user.id
    logger.info(
        f"Opening settings editor for user {user_id}, selected_index={selected_index}, is_experimental={is_experimental}"
    )

    async with await get_session() as session:
        try:
            result = await session.execute(
                db.select(Settings).filter_by(user_id=user_id)
            )
            settings = result.scalars().first()

            # Фильтруем настройки по типу
            if is_experimental:
                filter_condition = SettingDefinition.experimental == True
            else:
                filter_condition = SettingDefinition.experimental == False

            result = await session.execute(
                db.select(SettingDefinition)
                .filter_by(visible=True)
                .filter(filter_condition)
                .order_by(SettingDefinition.ordering)
            )
            definitions = result.scalars().all()

            if not definitions:
                text = "🧪 <b>Экспериментальные функции</b>\n\nНет доступных экспериментальных настроек"
                logger.info(
                    f"No {'experimental' if is_experimental else 'regular'} settings for user {user_id}"
                )

                if isinstance(message_or_callback, Message):
                    await message_or_callback.answer(
                        text, reply_markup=kb.back_to_main_settings
                    )
                else:
                    await message_or_callback.message.edit_text(
                        text, reply_markup=kb.back_to_main_settings
                    )
                return

            if selected_index > len(definitions) - 1:
                selected_index = 0
            elif selected_index < 0:
                selected_index = len(definitions) - 1

            selected_key = definitions[selected_index].key
            logger.debug(f"Selected setting: {selected_key}")

            title = (
                "🧪 <b>Экспериментальные настройки</b>"
                if is_experimental
                else "⚙️ <b>Основные настройки</b>"
            )
            text = f"{title}\n\n"
            text += await render_settings_text(
                definitions, settings, selected_key, is_experimental
            )
            keyboard = await kb.build_settings_nav_keyboard(
                user_id, definitions, selected_index, is_experimental
            )

            if isinstance(message_or_callback, Message):
                await message_or_callback.answer(text, reply_markup=keyboard)
            else:
                await message_or_callback.message.edit_text(text, reply_markup=keyboard)

            logger.info(f"Settings editor displayed for user {user_id}")

        except Exception as e:
            logger.exception(f"Error in settings editor for user {user_id}: {e}")


def get_error_message_by_status(status_code: int) -> str:
    if status_code == 408:
        logger.debug(f"Status code {status_code} -> 408 error message")
        return ERROR_408_MESSAGE
    elif status_code in [500, 501, 502]:
        logger.debug(f"Status code {status_code} -> 500 error message")
        return ERROR_500_MESSAGE
    else:
        logger.debug(f"Status code {status_code} -> default error message")
        return ERROR_MESSAGE


async def ensure_user_settings(session, user_id: int):
    logger.debug(f"Ensuring user settings exist for user {user_id}")

    try:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings = result.scalar_one_or_none()
        if not settings:
            session.add(Settings(user_id=user_id))
            await session.commit()
            logger.info(f"Created settings for user {user_id}")
        else:
            logger.debug(f"Settings already exist for user {user_id}")
    except Exception as e:
        logger.exception(f"Error ensuring user settings for {user_id}: {e}")


async def save_profile_data(session, user_id, profile_data, username):
    logger.info(f"Saving profile data for user {user_id}")

    try:
        result = await session.execute(db.select(UserData).filter_by(user_id=user_id))
        user_data: UserData = result.scalar_one_or_none()

        api, user = await get_student(user_id)
        if not api or not user:
            logger.error(f"Cannot get student data for user {user_id}")
            return

        profile = await api.get_family_profile(profile_id=user.profile_id)

        phone = profile.profile.phone
        if phone and not phone.startswith("7"):
            if phone.startswith("8"):
                phone = "7" + phone[1:]
                logger.debug(f"Phone number reformatted from 8 to 7: {phone}")
            else:
                phone = "7" + phone
                logger.debug(f"Phone number reformatted to 7: {phone}")
        elif not phone:
            phone = None

        email = profile.profile.email
        if not email:
            email = None

        if not user_data:
            user_data = UserData(
                user_id=user_id,
                first_name=profile_data.first_name,
                last_name=profile_data.last_name,
                middle_name=profile_data.middle_name,
                gender=profile_data.sex,
                phone=phone,
                email=email,
                birthday=profile_data.birth_date,
                username=username,
            )
            session.add(user_data)
            logger.info(f"Created new UserData record for user {user_id}")
        else:
            user_data.first_name = profile_data.first_name
            user_data.last_name = profile_data.last_name
            user_data.middle_name = profile_data.middle_name
            user_data.gender = profile_data.sex
            user_data.phone = phone
            user_data.email = email
            user_data.birthday = profile_data.birth_date
            user_data.username = username
            logger.info(f"Updated UserData record for user {user_id}")

        await session.commit()
        logger.success(f"Profile data saved successfully for user {user_id}")

    except Exception as e:
        logger.exception(f"Error saving profile data for user {user_id}: {e}")


async def parse_and_format_phone(raw_number: str) -> str:
    logger.debug(f"Parsing phone number: {raw_number}")

    try:
        raw_number = raw_number.strip()

        # Преобразуем "8" в "+7" (только если длина 11 и начинается с "8")
        if raw_number.startswith("8") and len(raw_number) == 11:
            raw_number = "+7" + raw_number[1:]
            logger.debug(f"Converted 8 to +7: {raw_number}")

        # Если просто начинается с "7" и длина 11, добавляем "+"
        elif raw_number.startswith("7") and len(raw_number) == 11:
            raw_number = "+" + raw_number
            logger.debug(f"Added + to 7: {raw_number}")

        # Если начинается с "00" (международный формат), заменим на "+"
        elif raw_number.startswith("00"):
            raw_number = "+" + raw_number[2:]
            logger.debug(f"Converted 00 to +: {raw_number}")

        # Парсим номер (без указания региона — универсально)
        phone = phonenumbers.parse(raw_number, None)

        if not phonenumbers.is_valid_number(phone):
            logger.warning(f"Invalid phone number: {raw_number}")
            return "Неверный номер"

        formatted = phonenumbers.format_number(
            phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL
        )
        logger.debug(f"Formatted phone number: {formatted}")
        return formatted

    except phonenumbers.NumberParseException:
        logger.error(f"Error parsing phone number {raw_number}: {e}")
        return "Н/Д"


async def generate_deeplink(args):
    deeplink = f"https://t.me/{config.BOT_USERNAME}?start={args}"
    logger.debug(f"Generated deeplink: {deeplink}")
    return deeplink


async def deep_links(message: Message, args, bot: Bot, state: FSMContext):
    logger.info(f"Processing deep link for user {message.from_user.id}, args: {args}")

    if args.startswith("done-homework-"):
        from app.utils.user.api.mes.homeworks import handle_homework_navigation

        homework_entry_id = args.split("-")[2]
        done = args.split("-")[3]
        done = True if done == "True" else False

        logger.debug(f"Homework completion: entry_id={homework_entry_id}, done={done}")

        api, user = await get_student(message.from_user.id)

        await message.delete()

        try:
            await api.done_homework(
                homework_entry_id=homework_entry_id,
                profile_id=user.profile_id,
                done=done,
            )
            logger.info(
                f"Homework {homework_entry_id} marked as done={done} for user {message.from_user.id}"
            )
        except Exception as e:
            logger.error(f"Error marking homework {homework_entry_id}: {e}")

        text, date, markup = await handle_homework_navigation(
            message.from_user.id, state, "to_date", subject_mode=False
        )

        await state.update_data(date=date)
        await message.answer(text, reply_markup=markup)

    elif args.startswith("subject-homework-"):
        from app.utils.user.api.mes.homeworks import handle_homework_navigation

        subject_id = int(args.split("-")[2])
        date = datetime.strptime(args.split("-")[3], "%d_%m_%Y")

        logger.debug(f"Subject homework: subject_id={subject_id}, date={date}")

        await message.delete()

        text, date, markup = await handle_homework_navigation(
            message.from_user.id,
            state,
            subject_mode=True,
            date=date,
            subject_id=subject_id,
        )

        await state.update_data(date=date)
        await state.update_data(subject_id=subject_id)

        await message.answer(text, reply_markup=markup)
        logger.info(f"Subject homework displayed for user {message.from_user.id}")

    elif args.startswith("subject-marks-"):
        from app.utils.user.api.mes.marks import get_marks_by_subject

        subject_id = int(args.split("-")[2])
        logger.debug(f"Subject marks: subject_id={subject_id}")

        await message.delete()

        text, periods = await get_marks_by_subject(message.from_user.id, subject_id=subject_id)

        await state.update_data(periods=periods)
        await state.update_data(subject_id=subject_id)

        await message.answer(text, reply_markup=kb.subject_marks)
        logger.info(f"Subject marks displayed for user {message.from_user.id}")

    elif args.startswith("autogdz-"):
        from app.utils.user.api.learnify.subscription import get_gdz_answers

        homework_id = int(args.split("-")[1])
        logger.debug(f"Auto GDZ: homework_id={homework_id}")

        await message.delete()

        async with await get_session() as session:
            try:
                result = await session.execute(
                    db.select(PremiumSubscription).filter_by(
                        user_id=message.from_user.id
                    )
                )
                premium_user = result.scalar_one_or_none()

                if not premium_user or not premium_user.is_active:
                    logger.warning(
                        f"User {message.from_user.id} tried to use GDZ without premium"
                    )
                    await message.answer(NO_PREMIUM_ERROR, reply_markup=kb.get_premium)
                    return

                result = await session.execute(
                    db.select(Homework).filter_by(id=homework_id)
                )
                homework = result.scalar_one_or_none()
                if not homework:
                    logger.error(
                        f"Homework {homework_id} not found for user {message.from_user.id}"
                    )
                    message.answer("❌ <b>Ошибка</b>\n\nДомашнее задание не найдено")
                    return

                result = await session.execute(
                    db.select(Gdz).filter_by(
                        user_id=message.from_user.id, subject_id=homework.subject_id
                    )
                )
                gdz_info = result.scalar_one_or_none()

                if not gdz_info:
                    logger.warning(
                        f"User {message.from_user.id} has no GDZ link for subject {homework.subject_id}"
                    )
                    text = "❌ <b>Не указана ссылка для автоматизации ГДЗ</b>\n\n"
                    return await message.answer(
                        text, reply_markup=kb.set_auto_gdz_links
                    )

                temp_message = await message.answer(f"🔄 Загрузка...")
                logger.debug(f"Fetching GDZ answers for homework {homework_id}")

                text, solutions = await get_gdz_answers(
                    user_id=message.from_user.id,
                    subject_id=homework.subject_id,
                    homework=homework,
                )

                await temp_message.delete()

                if not solutions:
                    logger.error(f"No solutions found for homework {homework_id}")
                    await message.answer(
                        "❌ <b>Ошибка</b>\n\nНе удалось получить ответы",
                        reply_markup=kb.delete_message,
                    )
                    return

                await message.answer(
                    text, reply_markup=kb.delete_message, protect_content=True
                )
                logger.info(
                    f"Found {len(solutions)} solutions for homework {homework_id}"
                )

                def chunked(iterable, n):
                    for i in range(0, len(iterable), n):
                        yield iterable[i : i + n]

                for num, solution in enumerate(solutions, 1):
                    images = solution["images"]
                    text = solution["text"]

                    image_chunks = list(chunked(images, 10))
                    total_parts = len(image_chunks)

                    for i, image_chunk in enumerate(image_chunks, start=1):
                        if total_parts > 1:
                            caption = f"{num}. {text}\n🧩 Часть {i}/{total_parts}"
                        else:
                            caption = f"{num}. {text}"

                        media_group = MediaGroupBuilder(caption=caption)
                        for image in image_chunk:
                            media_group.add_photo(media=image)

                        await message.answer_media_group(
                            media=media_group.build(), protect_content=True
                        )
                await message.answer(
                    text="✅ <b>Выдача завершена</b>", reply_markup=kb.delete_message
                )
                logger.success(f"GDZ answers sent for user {message.from_user.id}")
            except Exception as e:
                logger.exception(
                    f"Error in autogdz for user {message.from_user.id}: {e}"
                )

    elif args.startswith("subject-menu-"):
        subject_id = int(args.split("-")[2])
        date = datetime.strptime(args.split("-")[3], "%d_%m_%Y")

        logger.debug(f"Subject menu: subject_id={subject_id}, date={date}")

        await message.delete()

        try:
            api, user = await get_student(message.from_user.id)
            subjects = await api.get_subjects(
                student_id=user.student_id, profile_id=user.profile_id
            )
            subject_name = next(
                (
                    subject.subject_name
                    for subject in subjects.payload
                    if subject.subject_id == subject_id
                ),
                "Неизвестный предмет",
            )

            logger.debug(f"Subject name: {subject_name}")

            text = (
                f"{await get_emoji_subject(subject_name)} <b>{subject_name}</b>\n\n"
                f"⚙️ Доступные разделы:\n"
                f"  • ⚡ <b>Быстрое ГДЗ</b>\n"
                f"  • 🏠 <b>Домашнее задание</b>\n"
                f"  • 🎯 <b>Оценки</b>\n"
                f"  • 📖 <b>Электронный учебник</b>\n"
            )

            await message.answer(
                text, reply_markup=await kb.subject_menu(subject_id, date)
            )
            logger.info(f"Subject menu displayed for user {message.from_user.id}")

        except Exception as e:
            logger.exception(
                f"Error displaying subject menu for user {message.from_user.id}: {e}"
            )

    else:
        logger.debug(f"Unknown deep link args: {args}")


# def build_year_stats_query(user_id: int, year: int):
#     return {
#         "size": 0,
#         "query": {
#             "bool": {
#                 "filter": [
#                     {"term": {"user.user_id": user_id}},  # ⬅️ важно
#                     {
#                         "range": {
#                             "timestamp": {
#                                 "gte": f"{year}-01-01T00:00:00",
#                                 "lte": f"{year}-12-31T23:59:59",
#                             }
#                         }
#                     }
#                 ]
#             }
#         },
#         "aggs": {
#             "total_actions": {
#                 "value_count": {"field": "action_type.keyword"}
#             },
#             "messages": {
#                 "filter": {
#                     "term": {"action_type.keyword": "message"}
#                 }
#             },
#             "callbacks": {
#                 "filter": {
#                     "term": {"action_type.keyword": "callback_query"}
#                 }
#             },
#             "active_days": {
#                 "cardinality": {
#                     "script": {
#                         "source": "doc['timestamp'].value.toLocalDate()"
#                     }
#                 }
#             },
#             "avg_processing_time": {
#                 "avg": {"field": "processing_time_ms"}
#             },
#             "first_seen": {
#                 "min": {"field": "timestamp"}
#             },
#             "last_seen": {
#                 "max": {"field": "timestamp"}
#             }
#         }
#     }

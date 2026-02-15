# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.types import InlineKeyboardButton, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.config.config import LEARNIFY_API_TOKEN
from app.utils.user.utils import get_emoji_subject, get_student


async def main(user_id):
    keyboard = ReplyKeyboardBuilder()

    keyboard.row(
        KeyboardButton(text="🔔 Уведомления"),
        KeyboardButton(text="📅 Расписание"),
    )
    keyboard.row(
        KeyboardButton(text="🎓 Оценки"),
        KeyboardButton(text="📚 Домашние задания"),
    )
    keyboard.row(
        KeyboardButton(text="📋 Меню"),
    )

    keyboard.row(KeyboardButton(text="⚙️ Настройки"))

    return keyboard.as_markup(resize_keyboard=True)


async def choice_subject(user_id, for_):
    api, user = await get_student(user_id)

    subjects = await api.get_subjects(
        student_id=user.student_id, profile_id=user.profile_id
    )

    keyboard = InlineKeyboardBuilder()

    for subject in subjects.payload:
        keyboard.row(
            InlineKeyboardButton(
                text=f"{await get_emoji_subject(subject.subject_name)} {subject.subject_name}",
                callback_data=f"select_subject_{for_}_{subject.subject_id}",
            )
        )

    keyboard = keyboard.adjust(2)

    keyboard.row(InlineKeyboardButton(text=f"↪️ Назад", callback_data=f"back_to_{for_}"))

    return keyboard.as_markup()


async def subject_menu(subject_id, date):
    keyboard = InlineKeyboardBuilder()

    if LEARNIFY_API_TOKEN:
        keyboard.row(
            InlineKeyboardButton(
                text="⚡️ Быстрое ГДЗ", callback_data=f"quick_gdz_{subject_id}"
            ),
            InlineKeyboardButton(
                text="🏠 ДЗ",
                callback_data=f"select_subject_homework_{subject_id}_{date.strftime("%d-%m-%Y")}_new",
            ),
        )
        keyboard.row(
            InlineKeyboardButton(
                text="🎯 Оценки", callback_data=f"select_subject_marks_{subject_id}_new"
            ),
            InlineKeyboardButton(
                text="📖 Учебник", callback_data=f"student_book_{subject_id}"
            ),
        )
    else:
        keyboard.row(
            InlineKeyboardButton(
                text="🏠 ДЗ",
                callback_data=f"select_subject_homework_{subject_id}_{date.strftime("%d-%m-%Y")}_new",
            ),
            InlineKeyboardButton(
                text="🎯 Оценки", callback_data=f"select_subject_marks_{subject_id}_new"
            ),
        )
    keyboard.row(InlineKeyboardButton(text="Закрыть", callback_data="delete_message"))

    return keyboard.as_markup()

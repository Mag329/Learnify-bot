# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

mark = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="mark_left"),
            InlineKeyboardButton(text="📅", callback_data="mark_today"),
            InlineKeyboardButton(text="➡️", callback_data="mark_right"),
        ],
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_marks"
            ),
        ],
    ]
)

subject_marks = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_marks"
            ),
        ],
        [InlineKeyboardButton(text=f"↪️ Назад", callback_data=f"back_to_marks")],
    ]
)

subject_marks_with_close = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_marks"
            ),
        ],
        [InlineKeyboardButton(text=f"Закрыть", callback_data=f"delete_message")],
    ]
)

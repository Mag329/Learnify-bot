# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

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
            InlineKeyboardButton(
                text="📅 Сменить период", callback_data="choose_period_marks"
            )
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
            InlineKeyboardButton(
                text="📅 Сменить период", callback_data="choose_period_marks"
            )
        ],
        [InlineKeyboardButton(text=f"Закрыть", callback_data=f"delete_message")],
    ]
)

async def get_marks_periods_keyboard(periods, active_period):
    builder = InlineKeyboardBuilder()
    
    for period in periods:
        builder.button(text=f"{'⚫️ ' if period['num'] == active_period else ''}{period['title']}", callback_data=f"select_period_marks_{period['num']}")
    
    builder.button(text=f'{'⚫️ ' if active_period == -1 else ''}🗓️ Год', callback_data='select_period_marks_year')
    
    if len(periods) <= 2:
        builder.adjust(1, 1, 1)
    elif len(periods) == 3:
        builder.adjust(2, 1, 1, 1)
    elif len(periods) == 4:
        builder.adjust(2, 2, 1, 1)
        
    return builder.as_markup()
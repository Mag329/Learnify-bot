# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config.config import LEARNIFY_API_TOKEN


async def menu():
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text="📊 Посещаемость", callback_data="visits"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
    )
    keyboard.row(
        InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_rank_class"),
        InlineKeyboardButton(text="🏆 Итоги", callback_data="results"),
    )
    if LEARNIFY_API_TOKEN:
        keyboard.row(
            InlineKeyboardButton(text="💎 Подписка", callback_data="subscription_page")
        )

    return keyboard.as_markup()


visits = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="visits_left"),
            InlineKeyboardButton(text="📅", callback_data="visits_this_week"),
            InlineKeyboardButton(text="➡️", callback_data="visits_right"),
        ],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

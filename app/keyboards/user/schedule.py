from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

schedule = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="schedule_left"),
            InlineKeyboardButton(text="📅", callback_data="schedule_today"),
            InlineKeyboardButton(text="➡️", callback_data="schedule_right"),
        ],
    ]
)

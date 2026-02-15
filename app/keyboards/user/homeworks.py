from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

homework = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="homework_left"),
            InlineKeyboardButton(text="📅", callback_data="homework_today"),
            InlineKeyboardButton(text="➡️", callback_data="homework_right"),
        ],
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_homework"
            ),
        ],
    ]
)

subject_homework = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="subject_homework_left"),
            InlineKeyboardButton(text="📅", callback_data="subject_homework_today"),
            InlineKeyboardButton(text="➡️", callback_data="subject_homework_right"),
        ],
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_homework"
            ),
        ],
        [InlineKeyboardButton(text=f"↪️ Назад", callback_data=f"back_to_homework")],
    ]
)

subject_homework_with_close = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="subject_homework_left"),
            InlineKeyboardButton(text="📅", callback_data="subject_homework_today"),
            InlineKeyboardButton(text="➡️", callback_data="subject_homework_right"),
        ],
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_homework"
            ),
        ],
        [InlineKeyboardButton(text=f"Закрыть", callback_data=f"delete_message")],
    ]
)

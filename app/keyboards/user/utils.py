from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

back_to_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")]
    ]
)

delete_message = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
    ]
)

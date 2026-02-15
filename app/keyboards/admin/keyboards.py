from datetime import datetime

from aiogram.types import (InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.utils.database import Settings, db, get_session

panel = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Уведомление", callback_data="update_notification")],
        [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")],
    ]
)

back_to_admin_panel = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_admin_panel")]
    ]
)

confirm_update_notification = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Отправить", callback_data="send_update_notification"
            )
        ],
        [
            InlineKeyboardButton(
                text="Отменить", callback_data="cancel_update_notification"
            )
        ],
    ]
)

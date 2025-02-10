from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from datetime import datetime

from app.utils.database import AsyncSessionLocal, db, Settings


panel = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Уведомление об обновление", callback_data="update_notification"
            )
        ],
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

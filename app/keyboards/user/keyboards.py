from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from datetime import datetime

from app.utils.database import AsyncSessionLocal, db, Settings


start_command = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Войти", callback_data="login")],
    ]
)

homework = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="homework_left"),
            InlineKeyboardButton(text="📅", callback_data="homework_today"),
            InlineKeyboardButton(text="➡️", callback_data="homework_right"),
        ],
    ]
)

schedule = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="schedule_left"),
            InlineKeyboardButton(text="📅", callback_data="schedule_today"),
            InlineKeyboardButton(text="➡️", callback_data="schedule_right"),
        ],
    ]
)

mark = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="mark_left"),
            InlineKeyboardButton(text="📅", callback_data="mark_today"),
            InlineKeyboardButton(text="➡️", callback_data="mark_right"),
        ],
    ]
)

notifications_new = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Новые", callback_data="notifications_new")]
    ]
)

notifications_all = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📩 Все", callback_data="notifications_all")]
    ]
)

menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📊 Посещаемость", callback_data="visits")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
    ]
)

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


async def user_settings(user_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings = result.scalar_one_or_none()

        keyboard = InlineKeyboardBuilder()

        keyboard.row(
            InlineKeyboardButton(
                text=f'Уведомления о новых оценках {"✅" if settings.enable_new_mark_notification else "❌"}',
                callback_data="enable_new_mark_notification_settings",
            )
        )
        
        keyboard.row(
            InlineKeyboardButton(
                text=f'Уведомления о новых ДЗ {"✅" if settings.enable_homework_notification else "❌"}',
                callback_data="enable_homework_notification_settings",
            )
        )  
        
        # keyboard.row(
        #     InlineKeyboardButton(
        #         text=f'Экспериментальные функции {"✅" if settings.experimental_features else "❌"}',
        #         callback_data="experimental_features_settings",
        #     )
        # )

        keyboard.row(
            InlineKeyboardButton(
                text="🚪 Выйти из аккаунта", callback_data="exit_from_account"
            )
        )

        return keyboard.as_markup()

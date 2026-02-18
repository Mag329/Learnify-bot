# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config.config import BUG_REPORT_URL
from app.utils.database import Settings, db, get_session


async def build_settings_nav_keyboard(
    user_id, definitions, selected_index, is_experimental=False
):
    async with await get_session() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings: Settings = result.scalar()

    selected_key = definitions[selected_index].key

    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text="🔼",
            callback_data=f"nav_up_settings:{selected_index}:{'experimental' if is_experimental else 'main'}",
        ),
        InlineKeyboardButton(
            text="🔽",
            callback_data=f"nav_down_settings:{selected_index}:{'experimental' if is_experimental else 'main'}",
        ),
    )
    keyboard.row(
        InlineKeyboardButton(
            text="✏️ Изменить",
            callback_data=f"edit_settings:{selected_index}:{selected_key}:{'experimental' if is_experimental else 'main'}",
        )
    )

    if settings and settings.experimental_features:
        if is_experimental:
            keyboard.row(
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="back_to_main_settings"
                )
            )
        else:
            keyboard.row(
                InlineKeyboardButton(
                    text="🧪 Экспериментальные функции",
                    callback_data="show_experimental_settings",
                )
            )
            if settings.use_cache:
                keyboard.row(
                    InlineKeyboardButton(
                        text="📦 Очистить кэш", callback_data="clear_cache"
                    )
                )

    keyboard.row(InlineKeyboardButton(text="🤖 О боте", callback_data="about_bot"))
    keyboard.row(InlineKeyboardButton(text="🪲 Нашли ошибку?", url=BUG_REPORT_URL))

    keyboard.row(
        InlineKeyboardButton(
            text="🚪 Выйти из аккаунта", callback_data="exit_from_account"
        )
    )

    return keyboard.as_markup()


back_to_main_settings = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔙 Назад", callback_data="back_to_main_settings"
            )
        ]
    ]
)
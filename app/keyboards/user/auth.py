# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.config.config import BOT_CHANNEL, LEARNIFY_WEB

start_command = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Войти", callback_data="choose_login")],
    ]
)

choice_auth_variant = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🧑‍💻 Войти по логину", callback_data="auth_with_login"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔐 Войти по токену", callback_data="auth_with_token"
            )
        ],
        [
            InlineKeyboardButton(
                text="📷 Войти по QR-коду", callback_data="auth_with_qr"
            )
        ],
    ]
)

token_auth = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔑 Получить токен", url=f"{LEARNIFY_WEB}/api/v1/auth/method/token"
            )
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="choose_login")],
    ]
)

back_to_choose_auth = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="choose_login")]
    ]
)

reauth = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚪 Выйти из аккаунта", callback_data="exit_from_account"
            )
        ]
    ]
)

confirm_exit = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да", callback_data="confirm_exit_from_account"
            ),
            InlineKeyboardButton(
                text="❌ Нет", callback_data="decline_exit_from_account"
            ),
        ],
    ]
)

link_to_channel = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔗 Перейти в канал", url=BOT_CHANNEL
            )
        ]
    ]
)

check_subscribe = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔗 Перейти в канал", url=BOT_CHANNEL
            )
        ],
        [InlineKeyboardButton(text="🔎 Проверить", callback_data="check_subscription")],
    ]
)

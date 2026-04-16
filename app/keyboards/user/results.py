# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.utils.user.api.mes.results import get_period_display_name

get_results = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Подвести итоги", callback_data="results")],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)


async def get_periods_keyboard(period_type, available_periods=None):
    builder = InlineKeyboardBuilder()

    if period_type == "quarters":
        all_periods = [
            ("1️⃣", "1 четверть", 1),
            ("2️⃣", "2 четверть", 2),
            ("3️⃣", "3 четверть", 3),
            ("4️⃣", "4 четверть", 4),
        ]
    elif period_type == "half_years":
        all_periods = [("1️⃣", "1 полугодие", 1), ("2️⃣", "2 полугодие", 2)]
    elif period_type == "trimesters":
        all_periods = [
            ("1️⃣", "1 триместр", 1),
            ("2️⃣", "2 триместр", 2),
            ("3️⃣", "3 триместр", 3),
        ]
    else:
        all_periods = [("1️⃣", "Период 1", 1), ("2️⃣", "Период 2", 2)]

    if available_periods is None:
        available_periods = [p[2] for p in all_periods]

    for emoji, label, period_num in all_periods:
        if period_num in available_periods:
            callback_data = f"choose_period_{period_num}"
            text = f"{emoji} {label}"
            builder.button(text=text, callback_data=callback_data)
        else:
            builder.button(
                text=f"⚫️ {label}", callback_data=f"period_not_available_{period_num}"
            )

    builder.button(text='🗓️ Год', callback_data="choose_period_year")
    
    builder.button(text="↪️ Назад", callback_data="back_to_menu")

    if len(all_periods) <= 2:
        builder.adjust(2, 1)
    elif len(all_periods) == 3:
        builder.adjust(2, 1, 1, 1)
    elif len(all_periods) == 4:
        builder.adjust(2, 2, 1, 1)

    return builder.as_markup()


async def get_results_keyboard(period_type, current_period):
    """Генерирует основную клавиатуру для результатов"""
    builder = InlineKeyboardBuilder()

    builder.button(text="⬅️", callback_data="results_left")
    builder.button(text="➡️", callback_data="results_right")

    builder.button(text="♻️ Обновить", callback_data="refresh_results")
    builder.button(text="🏆 Общие итоги", callback_data="overall_results")

    # Информация о текущем периоде
    builder.button(text=f"📅 Сменить", callback_data="choose_period")
    builder.button(
        text=f"📍 {(await get_period_display_name(period_type, current_period)).capitalize()}", callback_data="current_period_info"
    )
    builder.button(text="↪️ Назад", callback_data="back_to_menu")

    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


async def get_overall_results_keyboard(
    period_type, current_period, has_more_lines=False
):
    builder = InlineKeyboardBuilder()

    if has_more_lines:
        builder.button(text="⬇️ Показать еще", callback_data="next_line_results")
        builder.button(text="📋 Показать все", callback_data=("show_all_lines_results"))

    builder.button(text="📚 Итоги по предметам", callback_data="subjects_results")

    builder.button(text=f"📅 Сменить", callback_data="choose_period")
    builder.button(
        text=f"📍 {(await get_period_display_name(period_type, current_period)).capitalize()}", callback_data="current_period_info"
    )
    builder.button(text="♻️ Обновить", callback_data="refresh_results")
    builder.button(text="↪️ Назад", callback_data="back_to_menu")

    if has_more_lines:
        builder.adjust(1, 1, 2, 1)
    else:
        builder.adjust(1, 2, 1)

    return builder.as_markup()

# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from app.utils.user.api.mes.homeworks import get_homework
from app.utils.user.api.mes.replaces import get_replaces

router = Router()


@router.inline_query()
async def inline_menu(inline_query: InlineQuery):
    user_id = inline_query.from_user.id

    results = [
        InlineQueryResultArticle(
            id="send_hw_today",
            title="📚 Отправить ДЗ",
            description="Загрузить домашнее задание на сегодня",
            input_message_content=InputTextMessageContent(
                message_text=(await get_homework(user_id, datetime.now(), "today"))[0]
            ),
        ),
        InlineQueryResultArticle(
            id="send_hw_tomorrow",
            title="📚 Отправить ДЗ",
            description="Загрузить домашнее задание на завтра",
            input_message_content=InputTextMessageContent(
                message_text=(
                    await get_homework(
                        user_id, datetime.now() + timedelta(days=1), "today"
                    )
                )[0]
            ),
        ),
        InlineQueryResultArticle(
            id="send_replacements_today",
            title="🔄 Замены на сегодня",
            description="Показать замены на сегодня",
            input_message_content=InputTextMessageContent(
                message_text=await get_replaces(user_id, datetime.now())
            ),
        ),
        InlineQueryResultArticle(
            id="send_replacements_tomorrow",
            title="🔄 Замены на завтра",
            description="Показать замены на завтра",
            input_message_content=InputTextMessageContent(
                message_text=await get_replaces(
                    user_id, datetime.now() + timedelta(days=1)
                )
            ),
        ),
    ]

    await inline_query.answer(results, cache_time=0, is_personal=True)

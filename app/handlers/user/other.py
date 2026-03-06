# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message
from elasticsearch import AsyncElasticsearch
from loguru import logger

from app.keyboards import user as kb
from app.config.config import BOT_VERSION, DEVELOPER, BOT_CHANNEL

# from app.utils.user.utils import build_year_stats_query, get_student

router = Router()


@router.callback_query(F.data == "about_bot")
async def about_bot(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    logger.info(f"User {user_id} requested bot information")
    
    text = f"🤖 <b>Информация о боте</b>\n    - 📦 <b>Версия бота:</b> {BOT_VERSION}\n    - 👨‍💻 <b>Разработчик:</b> {DEVELOPER}\n    - 📫 <b>Канал бота:</b> {BOT_CHANNEL}"

    await callback.answer()
    await callback.message.answer(
        text, reply_markup=kb.delete_message, disable_web_page_preview=True
    )

    logger.debug(f"Bot info sent to user {user_id}")

# es = AsyncElasticsearch("http://192.168.3.134:9200")
# INDEX_NAME = "bot_stats"


# @router.message(F.text == '/year_stats')
# async def year_stats(message: Message):
#     user_id = message.from_user.id
#     year = datetime.utcnow().year
#     user_id = 1459292756
#     query = build_year_stats_query(user_id, year)
#     response = await es.search(index=INDEX_NAME, body=query)

#     aggs = response["aggregations"]

#     text = (
#         f"🎉 *Ваш {year} год с Learnify*\n\n"
#         f"📩 Сообщений: *{aggs['messages']['doc_count']}*\n"
#         f"🧠 Нажатий кнопок: *{aggs['callbacks']['doc_count']}*\n"
#         f"⚡ Всего действий: *{aggs['total_actions']['value']}*\n"
#         f"📆 Активных дней: *{aggs['active_days']['value']}*\n"
#         f"⏱ Среднее время ответа: "
#         f"*{round(aggs['avg_processing_time']['value'] or 0)} мс*\n\n"
#         f"🚀 С нами с: *{aggs['first_seen']['value_as_string'][:10]}*"
#     )

#     await message.answer(text, parse_mode="Markdown")


@router.message(F.text)
async def unknown_handler(message: Message):
    await message.answer("❌ <b>Неизвестная команда</b>\nВведите /start")


@router.callback_query(F.data == "delete_message")
async def delete_message_handler(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await callback.message.delete()

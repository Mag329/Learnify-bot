from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

import app.keyboards.user.keyboards as kb
from app.config.config import BOT_VERSION, DEVELOPER, DEVELOPER_SITE

router = Router()


@router.callback_query(F.data == "about_bot")
async def about_bot(callback: CallbackQuery):
    text = f"🤖 <b>Информация о боте</b>\n    - 📦 <b>Версия бота:</b> {BOT_VERSION}\n    - 👨‍💻 <b>Разработчик:</b> {DEVELOPER}\n    - 🌐 <b>Сайт разработчика:</b> {DEVELOPER_SITE}"

    await callback.answer()
    await callback.message.answer(
        text, reply_markup=kb.delete_message, disable_web_page_preview=True
    )


@router.message(F.text)
async def unknown_handler(message: Message):
    await message.answer("❌ <b>Неизвестная команда</b>\nВведите /start")


@router.callback_query(F.data == "delete_message")
async def delete_message_handler(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await callback.message.delete()

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

router = Router()


@router.message(F.text)
async def unknown_handler(message: Message):
    await message.answer("❌ <b>Неизвестная команда</b>\nВведите /start")


@router.callback_query(F.data == "delete_message")
async def delete_message_handler(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await callback.message.delete()

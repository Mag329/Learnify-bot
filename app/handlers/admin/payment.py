
from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from app.utils.admin.utils import admin_required
import app.keyboards.user.keyboards as kb

router = Router()



@router.message(Command('refund'))
@admin_required
async def refund_handler(message: Message, command: CommandObject, bot: Bot):
    try:
        await bot.refund_star_payment(
            user_id=message.from_user.id,
            telegram_payment_charge_id=command.args
        )
    except TelegramBadRequest as e:
        if e.message == 'Bad Request: CHARGE_ALREADY_REFUNDED':
            await message.answer(
                '❌ Платеж уже возвращен',
                reply_markup=kb.delete_message
            )
        
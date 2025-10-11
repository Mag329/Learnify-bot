
from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from app.utils.admin.utils import admin_required

router = Router()



@router.message(Command('refund'))
@admin_required
async def refund_handler(message: Message, command: CommandObject, bot: Bot):
    await bot.refund_star_payment(
        user_id=message.from_user.id,
        telegram_payment_charge_id=command.args
    )
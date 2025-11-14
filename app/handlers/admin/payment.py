
from aiogram import Bot, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest

from app.config import config
from app.utils.admin.utils import admin_required
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, PremiumSubscriptionPlan, User, db, PremiumSubscription
from app.utils.user.api.learnify.subscription import create_subscription, disable_subscription

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
        
        
@router.message(Command('give_sub'))
@admin_required
async def give_sub_handler(message: Message, command: CommandObject, bot: Bot):
    if not command.args:
        await message.answer("❗ Формат: /give_sub <user_id|id1,id2,...|all> <plan_name> [message]")
        return
    
    data = command.args.split(maxsplit=2)
    
    if len(data) < 2:
        await message.answer("❗ Формат: /give_sub <user_id|id1,id2,...|all> <plan_name> [message]")
        return
    
    user_id_raw = data[0]
    plan_name = data[1]
    message_sub = data[2] if len(data) > 2 else None

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(PremiumSubscriptionPlan).filter_by(name=plan_name)
        )
        plan = result.scalar_one_or_none()
        if not plan:
            return await message.answer(f"❌ Подписка '{plan_name}' не найдена")

        if user_id_raw == "all":
            result = await session.execute(db.select(User).filter_by(role='student'))
            users = result.scalars().all()
        else:
            try:
                user_ids = [int(uid.strip()) for uid in user_id_raw.split(",") if uid.strip().isdigit()]
            except ValueError:
                return await message.answer("❌ Указан неверный формат user_id")
            
            if not user_ids:
                return await message.answer("❌ Не указаны корректные ID пользователей")

            result = await session.execute(
                db.select(User).filter(User.user_id.in_(user_ids))
            )
            users = result.scalars().all()

        if not users:
            return await message.answer("❌ Пользователи не найдены")

        success_count = 0
        failed_count = 0

        for user in users:
            try:
                result = await session.execute(
                    db.select(PremiumSubscription).filter_by(user_id=user.user_id)
                )
                premium_user = result.scalar_one_or_none()

                if not premium_user:
                    premium_user = PremiumSubscription(
                        user_id=user.user_id,
                        is_active=False
                    )
                    session.add(premium_user)
                    await session.commit()

                result, msg = await create_subscription(
                    session=session,
                    user_id=user.user_id,
                    plan=plan,
                    premium_user=premium_user
                )

                if msg:
                    failed_count += 1
                    continue

                recipient_text = (
                    f"🎁 <b>Вам была выдана подписка на {plan.text_name}!</b>\n\n"
                    f"👤 <b>Отправитель:</b> @{config.BOT_USERNAME}\n"
                )

                if message_sub:
                    recipient_text += f"💬 <b>Сообщение:</b> <i>{message_sub}</i>\n\n"

                recipient_text += (
                    f"🗓️ <b>Подписка активна до:</b> <i>{result.expires_at.strftime('%d %B %Y %H:%M')}</i>\n\n"
                    "✨ Наслаждайтесь всеми преимуществами подписки и удачного обучения!"
                )

                try:
                    await bot.send_message(chat_id=user.user_id, text=recipient_text)
                except Exception:
                    pass

                success_count += 1

            except Exception:
                failed_count += 1
                continue

        await session.commit()

        await message.answer(
            f"✅ Подписка '{plan_name}' выдана!\n"
            f"📬 Успешно: <b>{success_count}</b>\n"
            f"⚠️ Ошибок: <b>{failed_count}</b>"
        )
        
        
@router.message(Command('disable_sub'))
@admin_required
async def disable_sub_handler(message: Message, command: CommandObject, bot: Bot):
    if not command.args:
        await message.answer("❗ Формат: /disable_sub <user_id|id1,id2,...|all> <reason>")
        return
    
    data = command.args.split(maxsplit=1)
    
    if len(data) < 1:
        await message.answer("❗ Формат: /give_sub <user_id|id1,id2,...|all> <plan_name> [message]")
        return
    
    user_id_raw = data[0]
    reason = data[1] if len(data) > 1 else None

    async with AsyncSessionLocal() as session:
        if user_id_raw == "all":
            result = await session.execute(db.select(User).filter_by(role='student'))
            users = result.scalars().all()
        else:
            try:
                user_ids = [int(uid.strip()) for uid in user_id_raw.split(",") if uid.strip().isdigit()]
            except ValueError:
                return await message.answer("❌ Указан неверный формат user_id")
            
            if not user_ids:
                return await message.answer("❌ Не указаны корректные ID пользователей")

            result = await session.execute(
                db.select(User).filter(User.user_id.in_(user_ids))
            )
            users = result.scalars().all()

        if not users:
            return await message.answer("❌ Пользователи не найдены")

        success_count = 0
        failed_count = 0

        for user in users:
            try:
                result = await session.execute(
                    db.select(PremiumSubscription).filter_by(user_id=user.user_id)
                )
                premium_user = result.scalar_one_or_none()

                if not premium_user or not premium_user.is_active:
                    failed_count += 1
                    continue

                status = await disable_subscription(user.user_id)

                if not status:
                    failed_count += 1
                    continue
                
                recipient_text = (
                    "⛔ <b>Ваша подписка была отключена.</b>\n\n"
                    f"📄 <b>Причина:</b> <i>{reason}</i>\n\n"
                    "Если вы считаете, что это ошибка, свяжитесь с поддержкой."
                )

                try:
                    await bot.send_message(chat_id=user.user_id, text=recipient_text)
                except:
                    pass

                success_count += 1

            except Exception:
                failed_count += 1
                continue

        await message.answer(
            f"✅ Отключение подписки завершено\n"
            f"📬 Успешно: <b>{success_count}</b>\n"
            f"⚠️ Ошибок: <b>{failed_count}</b>"
        )
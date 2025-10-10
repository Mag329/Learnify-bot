from aiogram import F, Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command, CommandObject
from datetime import datetime, timedelta

import app.keyboards.user.keyboards as kb
from app.states.user.states import SettingsEditStates
from app.utils.user.api.learnify.subscription import create_subscription, get_user_info
from app.utils.database import AsyncSessionLocal, db, PremiumSubscriptionPlan, PremiumSubscription, Transaction


router = Router()


@router.callback_query(F.data == "subscription_page")
async def subscription_page_handler(callback: CallbackQuery):
    subscription = await get_user_info(callback.from_user.id)
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=callback.from_user.id))
        premium_user = result.scalar_one_or_none()
        if not premium_user:
            premium_user = PremiumSubscription(
                user_id=callback.from_user.id,
                is_active=False
            )
            session.add(premium_user)
            await session.commit()
            await session.refresh(premium_user)
    
    await callback.answer()
    if subscription and subscription.is_active:
        text = (
            '💎 <b>Learnify Premium</b>\n\n'
            f'<b>Подписка действует до:</b> <i>{subscription.expires_at.strftime("%H:%M:%S %d %B %Y")}</i>\n\n'
            f'<b>Баланс:</b> {premium_user.balance} ⭐️'
        )
    else:
        text = (
            '💎 <b>Learnify Premium</b>\n\n'
            'Раскрой весь потенциал бота с Premium-подпиской!\n\n'
            f'<b>Баланс:</b> {premium_user.balance} ⭐️\n\n'
            '✨ <b>Доступно:</b>\n'
            '• Авто-ГДЗ — бот сам подгружает ответы для домашних заданий\n'
            '• Поддержка развития проекта ❤️\n\n'
            '💰 <b>Стоимость:</b> 100 ⭐️ в месяц'
        )
        
    await callback.message.edit_text(text=text, reply_markup=await kb.subscription_keyboard(callback.from_user.id, subscription))
    

@router.callback_query(F.data == "get_subscription")
async def get_subscription_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('💎 <b>Learnify Premium</b>\n\nВыберите тарифный план', reply_markup=await kb.choose_subscription_plan(callback.from_user.id))
    

@router.callback_query(F.data.startswith("subscription_plan_"))
async def subscription_plan_handler(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscriptionPlan).filter_by(name=callback.data.split("_")[2]))
        plan = result.scalar_one_or_none()
    await callback.message.answer_invoice(
        title="Learnify Premium",
        description=f"Learnify Premium на {plan.title}",
        prices=[LabeledPrice(label='XTR', amount=plan.price)],
        provider_token='',
        payload=f'{plan.id} for myself',
        currency='XTR',
        reply_markup=await kb.buy_subscription_keyboard(plan.id, 'myself')
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def test(message: Message):
    payload = message.successful_payment.invoice_payload.split()
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscriptionPlan).filter_by(id=int(payload[0])))
        plan = result.scalar_one_or_none()
    
    if payload[2] == 'myself':
        user_id = message.from_user.id

    async with AsyncSessionLocal() as session:
        if result:
            transaction = Transaction(
                user_id=user_id,
                operation_type='credit',
                amount=plan.price,
                telegram_transaction_id=message.successful_payment.telegram_payment_charge_id,
            )
            session.add(transaction)
            
            result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=message.from_user.id))
            premium_user = result.scalar_one_or_none()
            
            if premium_user.is_active:
                premium_user.expires_at = premium_user.expires_at + timedelta(days=plan.duration)
            else:
                premium_user.expires_at = datetime.now() + timedelta(days=plan.duration)
                premium_user.is_active = True
            
            await session.commit()
    
    result, user = await create_subscription(user_id=user_id, expires_at=premium_user.expires_at)
    
    
    text = (
        '✅ Подписка успешно оформлена!\n\n'
        f'🗓️ Срок действия подписки: <i>{result.expires_at.strftime("%H:%M:%S %d %B %Y")}</i>\n\n'
        'Спасибо за поддержку проекта 💙\n'
        'Приятного использования 🚀'
    )
    await message.answer(text)
    
    
@router.message(Command('refund'))
async def refund_handler(message: Message, command: CommandObject, bot: Bot):
    await bot.refund_star_payment(
        user_id=message.from_user.id,
        telegram_payment_charge_id=command.args
    )
from datetime import datetime, timedelta
import logging

from aiogram import F, Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, LabeledPrice, Message,
                           PreCheckoutQuery)

import app.keyboards.user.keyboards as kb
from app.states.user.states import ChooseAmountForPaymentState, ChooseUserForGiftState
from app.utils.database import (AsyncSessionLocal, PremiumSubscription,
                                PremiumSubscriptionPlan, Transaction, UserData, db)
from app.utils.user.api.learnify.subscription import (create_subscription,
                                                      get_user_info)

router = Router()
logger = logging.getLogger(__name__)


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
        else:
            premium_user.is_active = subscription.is_active
            premium_user.expires_at = subscription.expires_at.replace(tzinfo=None)
            
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
    await callback.message.edit_text('💎 <b>Learnify Premium</b>\n\nВыберите тарифный план', reply_markup=await kb.choose_subscription_plan('myself'))
    

@router.callback_query(F.data.startswith("subscription_plan_"))
async def subscription_plan_handler(callback: CallbackQuery):
    data = callback.data.split("_")
    type = data[3]
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscriptionPlan).filter_by(name=data[2]))
        plan = result.scalar_one_or_none()
    await callback.message.answer_invoice(
        title="Learnify Premium",
        description=f"Learnify Premium на {plan.text_name}",
        prices=[LabeledPrice(label='Оплата подписки', amount=plan.price)],
        provider_token='',
        payload=f'{plan.id} for {type}',
        currency='XTR',
        reply_markup=await kb.buy_subscription_keyboard(plan.id, type)
    )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext, bot: Bot):
    payload_parts = message.successful_payment.invoice_payload.split()
    telegram_payment_id = message.successful_payment.telegram_payment_charge_id
    user_id = message.from_user.id
    data = await state.get_data()
    
    operation_type = None
    plan = None
    amount = 0
    
    if payload_parts[0].startswith('replenish'):
        operation_type = 'replenish'
        amount = int(payload_parts[0].split('_')[1])
    else:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                db.select(PremiumSubscriptionPlan).filter_by(id=int(payload_parts[0]))
            )
            plan = result.scalar_one_or_none()

        if not plan:
            await message.answer("⚠️ Произошла ошибка: тарифный план не найден.")
            await bot.refund_star_payment(
                user_id=message.from_user.id,
                telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id
            )
            logger.error(f"Payment failed: plan not found (payload={payload_parts})")
            return

        if len(payload_parts) > 2 and payload_parts[2] == 'myself':
            operation_type = 'myself'
            amount = plan.price
        elif len(payload_parts) > 2 and payload_parts[2].startswith('gift'):
            recipient_user_id = int(payload_parts[2].split('-')[1])
            operation_type = 'gift'
            amount = plan.price
        else:
            await message.answer("⚠️ Ошибка в данных платежа. Попробуйте снова.")
            return


    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                db.select(PremiumSubscription).filter_by(user_id=user_id)
            )
            premium_user = result.scalar_one_or_none()
            
            # --- Тип: покупка подписки для себя ---
            if operation_type == 'myself':
                transaction_credit = Transaction(
                    user_id=user_id,
                    operation_type='credit',
                    amount=amount,
                    telegram_transaction_id=telegram_payment_id
                )
                transaction_debit = Transaction(
                    user_id=user_id,
                    operation_type='debit',
                    amount=amount
                )
                session.add_all([transaction_credit, transaction_debit])
                await session.commit()
                
                result, msg = await create_subscription(session=session, user_id=user_id, plan=plan, premium_user=premium_user)

                if msg:
                    await message.answer(f'❌ <b>Произошла ошибка:</b>\n{msg}')
                
                text = (
                    "✅ Подписка успешно оформлена!\n\n"
                    f"🗓️ Действует до: <i>{result.expires_at.strftime('%H:%M:%S %d %B %Y')}</i>\n\n"
                    "Спасибо за поддержку проекта ❤️\n"
                    "Приятного использования 🚀"
                )

            # --- Тип: пополнение баланса ---
            elif operation_type == 'replenish':
                transaction = Transaction(
                    user_id=user_id,
                    operation_type='credit',
                    amount=amount,
                    telegram_transaction_id=telegram_payment_id
                )
                session.add(transaction)

                premium_user.balance += amount
                await session.commit()

                text = (
                    f"✅ Баланс успешно пополнен!\n\n"
                    f"💳 Баланс: {premium_user.balance} ⭐️\n"
                    f"💰 Сумма пополнения: {amount} ⭐️\n\n"
                    "Спасибо за поддержку проекта ❤️\n"
                    "Приятного использования 🚀"
                )

            # --- Тип: подарок ---
            elif operation_type == 'gift':
                transaction_credit = Transaction(
                    user_id=user_id,
                    operation_type='credit',
                    amount=amount,
                    telegram_transaction_id=telegram_payment_id
                )
                transaction_debit = Transaction(
                    user_id=user_id,
                    operation_type='debit',
                    amount=amount
                )
                session.add_all([transaction_credit, transaction_debit])
                await session.commit()
                
                result, msg = await create_subscription(session=session, user_id=recipient_user_id, plan=plan, premium_user=premium_user)

                if msg:
                    await message.answer(f'❌ <b>Произошла ошибка:</b>\n{msg}')
                    return
                
                text = (
                    "🎁 Подарочная подписка успешно оформлена!\n\n"
                    f"@{data['username']} скоро получит уведомление о вашем подарке 💌"
                )
                
                recipient_text = (
                    f"🎁 <b>Вам подарили подписку на {plan.text_name}!</b>\n\n"
                    f"Подарок от: @{message.from_user.username}\n"
                    f"<blockquote>{data['description']}</blockquote>\n\n"
                    f"🗓️ Подписка активна до: <b>{result.expires_at.strftime('%d %B %Y %H:%M')}</b>\n\n"
                    "Приятного использования 🚀"
                )
                
                try:
                    chat = await bot.get_chat(recipient_user_id)
                    await bot.send_message(
                        chat_id=chat.id, text=recipient_text
                    )
                except Exception as e:
                    logger.error()
                    

            else:
                text = "⚠️ Неизвестный тип операции"
                await bot.refund_star_payment(
                    user_id=message.from_user.id,
                    telegram_payment_charge_id=message.successful_payment.telegram_payment_charge_id
                )

            await message.answer(text)

        except Exception as e:
            await session.rollback()
            logger.exception(f"Ошибка обработки успешного платежа: {e}")
            await message.answer("❌ Произошла ошибка при обработке платежа. Попробуйте позже")
            
            

@router.callback_query(F.data == "replenish_subscription")
async def replenish_subscription_handler(callback: CallbackQuery, state: FSMContext):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=callback.from_user.id))
        premium_user = result.scalar_one_or_none()
        
    await state.update_data(main_message_id=callback.message.message_id)
    await state.set_state(ChooseAmountForPaymentState.amount)
    
    await callback.answer()
    await callback.message.edit_text(f"💳 <b>Пополнение баланса</b>\n\nВаш текущий баланс: {premium_user.balance if premium_user.balance else 0} ⭐️\n\nВведите сумму, на которую хотите пополнить", reply_markup=kb.back_to_menu)
    
    
@router.message(F.text, StateFilter(ChooseAmountForPaymentState.amount))
async def amount_for_payment_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = message.text
    
    await message.delete()

    if not amount.isdigit():
        await message.edit_text("❌ <b>Ошибка</b>\nВведите число", reply_markup=kb.back_to_menu)
        return
    
    if int(amount) <= 0:
        await message.edit_text("❌ <b>Ошибка</b>\nСумма должна быть положительным числом", reply_markup=kb.back_to_menu)
        return
    
    amount = int(amount)
    
    await state.clear()
    
    await bot.delete_message(chat_id=message.from_user.id, message_id=data["main_message_id"])
    
    await message.answer_invoice(
        title="Learnify Premium",
        description=f"Пополнение баланса ({amount} ⭐️)",
        prices=[LabeledPrice(label='Пополнение баланса', amount=amount)],
        provider_token='',
        payload=f'replenish_{amount} for myself',
        currency='XTR',
        reply_markup=await kb.buy_subscription_keyboard(amount, 'replenish')
    )
    
    
@router.callback_query(F.data == "give_subscription")
async def give_subscription_handler(callback: CallbackQuery, state: FSMContext):
    await state.update_data(main_message_id=callback.message.message_id)
    await state.set_state(ChooseUserForGiftState.username)
    
    await callback.answer()
    await callback.message.edit_text(f'🎁 <b>Learnify Premium в подарок</b>\n\n✨ Введите @username пользователя, которому хотите сделать подарок', reply_markup=kb.back_to_menu)
    

@router.message(F.text, StateFilter(ChooseUserForGiftState.username))
async def username_for_gift_handler(message: Message, state: FSMContext, bot: Bot):
    if message.text.startswith('@'):
        data = await state.get_data()
        
        username = message.text[1:]
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(db.select(UserData).where(db.func.lower(UserData.username) == username.lower()))
            user = result.scalar_one_or_none()

            if not user:
                await message.answer("❌ Пользователь не найден", reply_markup=kb.back_to_menu)
                return
            if user.user_id == message.from_user.id:
                await message.answer(
                    "❌ Вы не можете подарить подписку себе 😉",
                    reply_markup=kb.back_to_menu
                )
                return
        
        await state.update_data(username=user.username)
        await state.update_data(user_id=user.user_id)
        await state.set_state(ChooseUserForGiftState.description)
        
        await message.delete()
        
        text = (
            f"🎁 <b>Learnify Premium в подарок</b>\n\n"
            f"👤 Получатель: @{user.username}\n\n"
            "💬 Напишите сообщение, которое будет приложено к подарку.\n"
            "Оно сделает подарок ещё приятнее ✨"
        )
        
        await bot.edit_message_text(chat_id=message.from_user.id, message_id=data["main_message_id"], text=text,  reply_markup=kb.back_to_menu)

       


@router.message(F.text, StateFilter(ChooseUserForGiftState.description))
async def description_for_gift_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    description = message.text.strip()

    await state.update_data(description=description)
    await state.set_state(None)
    
    await message.delete()
    
    text = (
        f"🎁 <b>Learnify Premium в подарок</b>\n\n"
        f"👤 Получатель: @{data['username']}\n"
        f"💬 Сообщение: <i>{description}</i>\n\n"
        "📦 Теперь выберите тарифный план"
    )
    
    await bot.edit_message_text(chat_id=message.from_user.id, message_id=data["main_message_id"], text=text,  reply_markup=await kb.choose_subscription_plan(f'gift-{data['user_id']}'))
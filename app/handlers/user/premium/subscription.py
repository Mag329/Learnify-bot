import io
import logging
import os
from datetime import datetime, timedelta
from loguru import logger

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from miniopy_async import Minio
from miniopy_async.error import S3Error

import app.keyboards.user.keyboards as kb
from app.config.config import MINIO_BUCKET_NAME, NO_PREMIUM_ERROR
from app.minio import client as minio_client
from app.states.user.states import (
    ChooseAmountForPaymentState,
    ChooseUserForGiftState,
    SelectBookState,
    SelectGdzUrlState,
)
from app.utils.database import (
    get_session,
    Gdz,
    PremiumSubscription,
    PremiumSubscriptionPlan,
    StudentBook,
    Transaction,
    UserData,
    db,
)
from app.utils.misc import sanitize_filename
from app.utils.user.api.learnify.subscription import (
    create_subscription,
    get_user_info,
    successful_payment,
)
from app.utils.user.utils import get_student

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "subscription_page")
async def subscription_page_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} opened subscription page")
    
    subscription = await get_user_info(user_id)

    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(user_id=user_id)
        )
        premium_user = result.scalar_one_or_none()
        if not premium_user:
            premium_user = PremiumSubscription(
                user_id=user_id, is_active=False
            )
            session.add(premium_user)
            logger.debug(f"Created new premium subscription record for user {user_id}")
        else:
            premium_user.is_active = subscription.is_active
            premium_user.expires_at = subscription.expires_at.replace(tzinfo=None)

        await session.commit()
        await session.refresh(premium_user)

    await callback.answer()
    if subscription and subscription.is_active:
        text = (
            "💎 <b>Learnify Premium</b>\n\n"
            f'<b>Подписка действует до:</b> <i>{subscription.expires_at.strftime("%H:%M:%S %d %B %Y")}</i>\n\n'
            f"<b>Баланс:</b> {premium_user.balance} ⭐️"
        )
        logger.debug(f"Active subscription for user {user_id}, expires: {subscription.expires_at}")
    else:
        text = (
            "💎 <b>Learnify Premium</b>\n\n"
            "Раскройте весь потенциал бота с подпиской <b>Premium</b>!\n\n"
            f"<b>Баланс:</b> {premium_user.balance} ⭐️\n\n"
            "✨ <b>Что доступно с Premium:</b>\n"
            "• 🧠 <b>Авто-ГДЗ</b> — бот автоматически подгружает ответы для домашних заданий\n\n"
            "• ⚡ <b>Быстрое ГДЗ</b> — быстрый доступ к ГДЗ по предмету через выбор номера или страницы\n\n"
            "• 📖 <b>Электронные учебники</b> — быстрый доступ к электронной версии учебника\n\n"
            "• ❤️ <b>Поддержка проекта</b> — вы помогаете развивать Learnify\n\n\n"
            "<i>Некоторые функции требуют дополнительной настройки перед использованием</i>\n\n"
            "💰 <b>Стоимость:</b> 100 ⭐️ в месяц"
        )
        logger.debug(f"No active subscription for user {user_id}")

    await state.update_data(main_message_id=callback.message.message_id)

    await callback.message.edit_text(
        text=text,
        reply_markup=await kb.subscription_keyboard(
            user_id, subscription
        ),
    )


@router.callback_query(F.data == "get_subscription")
async def get_subscription_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} started subscription purchase")
    
    await callback.answer()
    await callback.message.edit_text(
        "💎 <b>Learnify Premium</b>\n\nВыберите тарифный план",
        reply_markup=await kb.choose_subscription_plan("myself"),
    )


@router.callback_query(F.data.startswith("subscription_plan_"))
async def subscription_plan_handler(
    callback: CallbackQuery, state: FSMContext, bot: Bot
):
    user_id = callback.from_user.id
    data = callback.data.split("_")
    type = data[3]
    plan_name = data[2]
    
    logger.info(f"User {user_id} selected plan: {plan_name}, type: {type}")

    await state.update_data(type=type)

    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscriptionPlan).filter_by(name=plan_name)
        )
        plan = result.scalar_one_or_none()

        await state.update_data(plan=plan.id)
        logger.debug(f"Plan ID: {plan.id}, price: {plan.price}")

        text = (
            "⚠️ <b>Важная информация перед оплатой подписки</b>\n\n"
            "Пожалуйста, обратите внимание, что <b>отмена подписки не предусмотрена</b>.\n"
            "Если вы столкнулись с ошибками, некорректной работой бота или неполнотой предоставляемых услуг, "
            "необходимо обратиться к разработчику для решения проблемы.\n\n"
            "📌 Контакты разработчика доступны во вкладке <b>«О боте»</b>.\n\n"
            "Мы всегда готовы помочь и постараемся решить любые вопросы как можно быстрее. "
            "Оплата подразумевает ваше согласие с этими условиями."
        )

        await callback.answer()
        await callback.message.answer(text, reply_markup=kb.confirm_pay)


@router.callback_query(F.data == "confirm_pay")
async def confirm_pay_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id
    data = await state.get_data()

    if not (data.get("plan") or data.get("type")):
        logger.warning(f"User {user_id} confirm_pay without plan/type data")
        await callback.message.answer()
        await callback.message.edit_text(
            "💎 <b>Learnify Premium</b>\n\nВыберите тарифный план",
            reply_markup=await kb.choose_subscription_plan("myself"),
        )

    type = data.get("type")

    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscriptionPlan).filter_by(id=data.get("plan"))
        )
        plan = result.scalar_one_or_none()

        result = await session.execute(
            db.select(PremiumSubscription).filter_by(user_id=user_id)
        )
        user = result.scalar_one_or_none()

        payload = f"{plan.id} for {type}"
        logger.debug(f"Payment payload: {payload}")

        if user and user.balance < plan.price:
            amount_to_pay = plan.price - user.balance
            logger.info(f"User {user_id} needs to pay {amount_to_pay} stars, balance: {user.balance}")
            
            await callback.message.answer_invoice(
                title="Learnify Premium",
                description=f"Learnify Premium на {plan.text_name}",
                prices=[
                    LabeledPrice(
                        label="Оплата подписки", amount=amount_to_pay
                    )
                ],
                provider_token="",
                payload=payload,
                currency="XTR",
                reply_markup=await kb.buy_subscription_keyboard(plan.id, type),
            )
        else:
            logger.info(f"User {user_id} has sufficient balance ({user.balance}) for plan {plan.price}")
            user.balance -= plan.price
            await session.commit()

            state_data = await state.get_data()
            state_data["sender_username"] = callback.from_user.username

            await successful_payment(
                user_id, callback.message, None, payload, state_data, bot
            )


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    user_id = pre_checkout_query.from_user.id
    logger.debug(f"Pre-checkout for user {user_id}, invoice payload: {pre_checkout_query.invoice_payload}")
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    telegram_payment_id = message.successful_payment.telegram_payment_charge_id
    payload = message.successful_payment.invoice_payload
    
    logger.info(f"Successful payment for user {user_id}, payload: {payload}, charge_id: {telegram_payment_id}")
    
    data = await state.get_data()
    data["sender_username"] = message.from_user.username

    await successful_payment(
        user_id,
        message,
        telegram_payment_id,
        payload,
        data,
        bot,
    )


@router.callback_query(F.data == "replenish_subscription")
async def replenish_subscription_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(user_id=user_id)
        )
        premium_user = result.scalar_one_or_none()

    current_balance = premium_user.balance if premium_user and premium_user.balance else 0
    logger.info(f"User {user_id} starting balance replenishment, current balance: {current_balance}")
    
    await state.update_data(main_message_id=callback.message.message_id)
    await state.set_state(ChooseAmountForPaymentState.amount)

    await callback.answer()
    await callback.message.edit_text(
        f"💳 <b>Пополнение баланса</b>\n\nВаш текущий баланс: {premium_user.balance if premium_user.balance else 0} ⭐️\n\nВведите сумму, на которую хотите пополнить",
        reply_markup=kb.back_to_menu,
    )


@router.message(F.text, StateFilter(ChooseAmountForPaymentState.amount))
async def amount_for_payment_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    amount = message.text

    await message.delete()

    if not amount.isdigit():
        logger.warning(f"User {user_id} entered non-digit amount: {amount}")
        await message.edit_text(
            "❌ <b>Ошибка</b>\nВведите число", reply_markup=kb.back_to_menu
        )
        return

    if int(amount) <= 0:
        logger.warning(f"User {user_id} entered non-positive amount: {amount}")
        await message.edit_text(
            "❌ <b>Ошибка</b>\nСумма должна быть положительным числом",
            reply_markup=kb.back_to_menu,
        )
        return

    amount = int(amount)

    logger.info(f"User {user_id} requesting replenishment of {amount} stars")
    
    await state.clear()

    await bot.delete_message(
        chat_id=message.from_user.id, message_id=data["main_message_id"]
    )

    await message.answer_invoice(
        title="Learnify Premium",
        description=f"Пополнение баланса ({amount} ⭐️)",
        prices=[LabeledPrice(label="Пополнение баланса", amount=amount)],
        provider_token="",
        payload=f"replenish_{amount} for myself",
        currency="XTR",
        reply_markup=await kb.buy_subscription_keyboard(amount, "replenish"),
    )


@router.callback_query(F.data == "give_subscription")
async def give_subscription_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} starting gift subscription process")
    
    await state.update_data(main_message_id=callback.message.message_id)
    await state.set_state(ChooseUserForGiftState.username)

    await callback.answer()
    await callback.message.edit_text(
        f"🎁 <b>Learnify Premium в подарок</b>\n\n✨ Введите @username пользователя, которому хотите сделать подарок",
        reply_markup=kb.back_to_menu,
    )


@router.message(F.text, StateFilter(ChooseUserForGiftState.username))
async def username_for_gift_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    username_input = message.text
    
    if username_input.startswith("@"):
        data = await state.get_data()

        username = message.text[1:]
        
        logger.debug(f"User {user_id} searching for recipient: {username}")

        async with await get_session() as session:
            result = await session.execute(
                db.select(UserData).where(
                    db.func.lower(UserData.username) == username.lower()
                )
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.warning(f"Recipient {username} not found for user {user_id}")
                await message.answer(
                    "❌ Пользователь не найден", reply_markup=kb.back_to_menu
                )
                return
            if user.user_id == message.from_user.id:
                logger.warning(f"User {user_id} attempted to gift subscription to themselves")
                await message.answer(
                    "❌ Вы не можете подарить подписку себе 😉",
                    reply_markup=kb.back_to_menu,
                )
                return

        await state.update_data(username=user.username)
        await state.update_data(user_id=user.user_id)
        await state.set_state(ChooseUserForGiftState.description)

        logger.info(f"User {user_id} selected recipient @{user.username} (ID: {user.user_id})")
        
        await message.delete()

        text = (
            f"🎁 <b>Learnify Premium в подарок</b>\n\n"
            f"👤 Получатель: @{user.username}\n\n"
            "💬 Напишите сообщение, которое будет приложено к подарку.\n"
            "Оно сделает подарок ещё приятнее ✨"
        )

        await bot.edit_message_text(
            chat_id=message.from_user.id,
            message_id=data["main_message_id"],
            text=text,
            reply_markup=kb.back_to_menu,
        )


@router.message(F.text, StateFilter(ChooseUserForGiftState.description))
async def description_for_gift_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    data = await state.get_data()
    description = message.text.strip()

    logger.debug(f"User {user_id} added gift description: {description[:50]}...")
    
    await state.update_data(description=description)
    await state.set_state(None)

    await message.delete()

    text = (
        f"🎁 <b>Learnify Premium в подарок</b>\n\n"
        f"👤 Получатель: @{data['username']}\n"
        f"💬 Сообщение: <i>{description}</i>\n\n"
        "📦 Теперь выберите тарифный план"
    )

    await bot.edit_message_text(
        chat_id=message.from_user.id,
        message_id=data["main_message_id"],
        text=text,
        reply_markup=await kb.choose_subscription_plan(f"gift-{data['user_id']}"),
    )


@router.callback_query(F.data == "back_to_auto_gdz")
@router.callback_query(F.data == "back_to_book")
async def back_to_auto_gdz_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    logger.debug(f"User {user_id} returning to auto GDZ settings")
    
    from .settings import subscription_settings_handler
    return await subscription_settings_handler(callback)


@router.callback_query(F.data == "offer_contract")
async def offer_contract_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    logger.debug(f"User {user_id} requested offer contract")
    
    text = (
        "📄 <b>Договор оферты</b>\n\n"
        "1️⃣ Оплата подписки на <b>Learnify Premium</b> является акцептом настоящей оферты.\n\n"
        "2️⃣ Оплата подразумевает ваше согласие с тем, что <b>отмена подписки не предусмотрена</b>.\n\n"
        "3️⃣ В случае ошибок, некорректной работы бота или неполноты предоставляемых услуг, "
        "вы имеете право обратиться к разработчику для решения проблемы.\n\n"
        "4️⃣ Контакты разработчика доступны во вкладке <b>«О боте»</b>.\n\n"
        "5️⃣ Все спорные вопросы решаются в досудебном порядке путем переговоров.\n\n\n"
        "Оплата подписки подтверждает ваше согласие с данными условиями.\n\n"
    )
    await callback.answer()
    await callback.message.answer(text, reply_markup=kb.delete_message)

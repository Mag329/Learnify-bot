# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import json
from datetime import datetime, timedelta
from loguru import logger

from learnifyapi.client import LearnifyAPI
from learnifyapi.exceptions import APIError
from sqlalchemy.orm import selectinload

from app.keyboards import user as kb
from app.config.config import DEFAULT_LONG_CACHE_TTL, LEARNIFY_API_TOKEN
from app.utils.database import (
    get_session,
    Gdz,
    PremiumSubscription,
    PremiumSubscriptionPlan,
    Transaction,
    User,
    db,
)
from app.utils.scheduler import scheduler
from app.utils.user.cache import redis_client
from app.utils.user.decorators import handle_api_error


@handle_api_error()
async def get_user_info(user_id):
    logger.debug(f"Getting user info for user {user_id}")
    
    async with await get_session() as session:
        result = await session.execute(db.select(User).filter_by(user_id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"User {user_id} not found in database")
            return None

        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                info = await api.get_user(user_id)
                logger.debug(f"User info retrieved for {user_id}")
                return info
            except APIError as e:
                logger.error(f"Learnify API error for user {user_id}: {e}")
                return None


async def create_subscription(session, user_id, plan, premium_user):
    try:
        logger.info(f"Creating subscription for user {user_id}, plan: {plan.name if plan else 'None'}")
        
        result = await session.execute(db.select(User).filter_by(user_id=user_id))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"User {user_id} not found in database")
            return None, "Пользователь не найден"

        if not plan:
            logger.error(f"No plan provided for user {user_id}")
            return None, "Не удалось определить тарифный план"

        if not premium_user:
            logger.warning(f"PremiumSubscription not found for user {user_id}")
            return None, "Не найдена ваша подписка. Пожалуйста попробуйте позже"

        # Обновление подписки
        now = datetime.now()
        duration = timedelta(days=plan.duration)

        if premium_user.is_active and premium_user.expires_at:
            premium_user.expires_at += duration
            logger.info(f"Extending subscription for user {user_id}: +{plan.duration} days, new expiry: {premium_user.expires_at}")
        else:
            premium_user.expires_at = now + duration
            premium_user.is_active = True
            logger.info(f"New subscription activated for user {user_id}\nPlan: {plan.name}\nPrice: {plan.price}\nExpires: {premium_user.expires_at}")

        premium_user.plan = plan.id
        await session.commit()

        # Взаимодействие с Learnify API
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                result = await api.create_user(
                    user_id=user_id, expires_at=premium_user.expires_at
                )
                logger.debug(f"User created in Learnify API for {user_id}")
            except APIError as e:
                if e.status_code == 400:
                    logger.debug(f"User {user_id} already exists in Learnify API, updating")
                    result = await api.update_user(
                        user_id=user_id,
                        expires_at=premium_user.expires_at,
                        is_active=True,
                    )
                else:
                    logger.exception(f"Learnify API error for user {user_id}: {e}")
                    return (
                        None,
                        "Ошибка при активации подписки. Пожалуйста попробуйте позже",
                    )

        logger.success(f"Subscription activated successfully for user {user_id}")
        return result, None

    except Exception as e:
        await session.rollback()
        logger.exception(f"Unexpected error creating subscription for user {user_id}: {e}")
        return (
            None,
            "Произошла ошибка при оформлении подписки. Пожалуйста попробуйте позже",
        )


async def disable_subscription(user_id):
    logger.info(f"Disabling subscription for user {user_id}")
    
    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(user_id=user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"User {user_id} not found or no subscription")
            return None

        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                result = await api.deactivate_subscription(user_id)
                logger.success(f"Subscription deactivated for user {user_id}")
                return True if result else False
            except APIError as e:
                logger.error(f"Failed to deactivate subscription for user {user_id}: {e}")
                return None


@handle_api_error()
async def get_gdz_answers(user_id, subject_id, homework=None, number=None):
    logger.info(f"Getting GDZ answers for user {user_id}, subject_id={subject_id}, homework={'yes' if homework else 'no'}, number={number}")
    
    if not subject_id:
        logger.warning(f"No subject_id provided for user {user_id}")
        return None, None

    if homework:
        cache_key = f"auto_gdz:{user_id}:{homework.id}:{subject_id}"
    else:
        cache_key = f"auto_gdz:{user_id}:{number}:{subject_id}"

    cached_full = await redis_client.get(cache_key)
    if cached_full:
        logger.debug(f"Cache hit for GDZ answers: user {user_id}")
        data = json.loads(cached_full)
        return data["main_text"], data["solutions"]
    else:
        logger.debug(f"Cache miss for GDZ answers: user {user_id}")

    async with await get_session() as session:
        result = await session.execute(
            db.select(Gdz).filter_by(user_id=user_id, subject_id=subject_id)
        )
        gdz_info = result.scalar_one_or_none()
        
        if not gdz_info:
            logger.warning(f"No GDZ info found for user {user_id}, subject {subject_id}")
            return None, None

    try:
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            if homework:
                logger.debug(f"Searching GDZ by task text: {homework.task[:50]}...")
                gdz = await api.get_gdz_answers(
                    user_id=user_id,
                    task_text=homework.task,
                    book_url=gdz_info.book_url,
                    search_by=gdz_info.search_by,
                )
            else:
                logger.debug(f"Searching GDZ by number: {number}")
                gdz = await api.get_gdz_answers(
                    user_id=user_id,
                    number=number,
                    book_url=gdz_info.book_url,
                    search_by=gdz_info.search_by,
                )
    except Exception as e:
        logger.exception(f"Learnify API error for user {user_id}: {e}")
        return None, None

    main_text = f"🧠 <b>Авто-гдз</b>\n\n"

    main_text += (
        f"📖 <b>Текст задания:</b>\n <code>{gdz.task_text}</code>\n\n"
        if homework
        else ""
    )

    title_map = {"pages": "Страница", "numbers": "Номер", "paragraphs": "Параграф"}
    title_label = title_map.get(gdz_info.search_by, "Задание")

    solutions = []
    for solution in getattr(gdz, "solutions", []):
        text = (
            f"📘 <b>{title_label} {solution.page_number}</b>\n\n"
            f'🔗 <a href="{solution.answer_url}">Ссылка на ГДЗ</a>\n\n'
        )
        solutions.append({"text": text, "images": getattr(solution, "image_urls", [])})

        if not solutions:
            logger.info(f"No solutions found for user {user_id}")
            return (
                main_text + "⚠️ К сожалению, ответы по данному заданию не найдены 😔",
                [],
            )

    cache_data = {"main_text": main_text, "solutions": solutions}
    await redis_client.setex(cache_key, DEFAULT_LONG_CACHE_TTL, json.dumps(cache_data))
    logger.success(f"GDZ answers found and cached for user {user_id}, {len(solutions)} solutions")

    return main_text, solutions


async def renew_subscription(user_id, bot):
    logger.info(f"Processing subscription renewal for user {user_id}")
    
    async with await get_session() as session:
        try:
            result = await session.execute(
                db.select(PremiumSubscription)
                .options(selectinload(PremiumSubscription.plan_obj))
                .filter_by(user_id=user_id, is_active=True)
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.warning(f"Active subscription not found for user {user_id}")
                return

            plan = subscription.plan_obj
            if not plan:
                logger.error(f"Plan not found for subscription user_id={user_id}")
                return

            if (
                subscription.auto_renew
                and subscription.balance >= plan.price
                and plan.price > 0
            ):
                logger.info(f"Auto-renewing subscription for user {user_id}, balance: {subscription.balance}, price: {plan.price}")
                
                result, error = await create_subscription(
                    session=session,
                    user_id=user_id,
                    plan=plan,
                    premium_user=subscription,
                )

                if not error:
                    subscription.balance -= plan.price
                    subscription.expires_at = result.expires_at.replace(tzinfo=None)
                    await session.commit()

                    text = (
                        "✅ <b>Подписка успешно продлена!</b>\n\n"
                        f"🗓️ Новая дата окончания: <i>{subscription.expires_at.strftime('%H:%M %d.%m.%Y')}</i>\n"
                        f"💳 Баланс: <b>{subscription.balance:.0f} ⭐️</b>\n\n"
                        "Спасибо, что остаетесь с Learnify ❤️"
                    )

                    logger.success(f"Subscription renewed for user {user_id} until {subscription.expires_at}")

                    await schedule_renew_subscription(
                        subscription.user_id, subscription.expires_at, bot
                    )

                else:
                    text = (
                        "❌ <b>Ошибка при продлении подписки</b>\n\n" f"<i>{error}</i>"
                    )
                    logger.error(f"Renewal error for user {user_id}: {error}")

            else:
                # Отключение подписки
                logger.info(f"Deactivating subscription for user {user_id} (auto_renew={subscription.auto_renew}, balance={subscription.balance}, price={plan.price})")
                
                success = await disable_subscription(user_id)

                if success:
                    reason = (
                        "💰 Недостаточно средств для продления"
                        if subscription.auto_renew
                        else "⚙️ Автопродление отключено"
                    )
                    text = (
                        "❌ <b>Срок действия вашей подписки истек</b>\n\n"
                        f"{reason}\n"
                        f"💳 Баланс: {subscription.balance:.0f} ⭐️"
                    )
                    logger.info(f"Subscription deactivated for user {user_id}")
                else:
                    text = (
                        "⚠️ <b>Ошибка при отключении подписки</b>\n\n"
                        "Не удалось деактивировать подписку"
                    )
                    logger.error(f"Failed to deactivate subscription for user {user_id}")

            try:
                await bot.send_message(
                    chat_id=user_id, text=text, reply_markup=kb.delete_message
                )
                logger.debug(f"Notification sent to user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to send message to user {user_id}: {e}")

        except Exception as e:
            await session.rollback()
            logger.exception(f"Error in renew_subscription for user {user_id}: {e}")


async def schedule_renew_subscription(user_id: int, expires_at: datetime, bot):
    job_id = f"renew_subscription_{user_id}"
    logger.info(f"Scheduling subscription renewal for user {user_id} at {expires_at}, job_id: {job_id}")
    
    if expires_at < datetime.now():
        logger.warning(f"Subscription for user {user_id} already expired, renewing immediately")
        await renew_subscription(user_id, bot)
    else:
        scheduler.add_job(
            renew_subscription,
            "date",
            run_date=expires_at,
            args=[user_id, bot],
            id=job_id,
            replace_existing=True,
        )
        logger.debug(f"Renewal job scheduled for user {user_id}")


async def delete_renew_subscription_task(user_id):
    job_id = f"renew_subscription_{user_id}"
    logger.debug(f"Deleting renewal task for user {user_id}, job_id: {job_id}")

    try:
        scheduler.remove_job(job_id)
        logger.debug(f"Renewal task deleted for user {user_id}")
    except Exception as e:
        logger.debug(f"No renewal task found for user {user_id} to delete: {e}")


async def restore_renew_subscription_jobs(bot):
    logger.info("Restoring scheduled subscription renewal jobs")
    
    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(is_active=True)
        )
        users = result.scalars().all()
        logger.info(f"Found {len(users)} active subscriptions to restore")
        
        restored_count = 0
        for user in users:
            try:
                await schedule_renew_subscription(user.user_id, user.expires_at, bot)
                restored_count += 1
                logger.debug(f"Restored renewal job for user {user.user_id}")
            except Exception as e:
                logger.error(f"Failed to restore renewal job for user {user.user_id}: {e}")
        
        logger.success(f"Restored {restored_count}/{len(users)} renewal jobs")


async def successful_payment(user_id, message, telegram_payment_id, payload, data, bot):
    logger.info(f"Processing successful payment for user {user_id}, payload: {payload}")
    
    payload_parts = payload.split()

    operation_type = None
    plan = None
    amount = 0

    if payload_parts[0].startswith("replenish"):
        operation_type = "replenish"
        amount = int(payload_parts[0].split("_")[1])
        logger.debug(f"Payment type: replenish, amount: {amount}")
    else:
        async with await get_session() as session:
            result = await session.execute(
                db.select(PremiumSubscriptionPlan).filter_by(id=int(payload_parts[0]))
            )
            plan = result.scalar_one_or_none()

        if not plan:
            await message.answer("⚠️ Произошла ошибка: тарифный план не найден.")
            await bot.refund_star_payment(
                user_id=user_id, telegram_payment_charge_id=telegram_payment_id
            )
            logger.error(f"Payment failed: plan not found (payload={payload})")
            return

        if len(payload_parts) > 2 and payload_parts[2] == "myself":
            operation_type = "myself"
            amount = plan.price
            logger.debug(f"Payment type: self subscription, plan: {plan.name}")
        elif len(payload_parts) > 2 and payload_parts[2].startswith("gift"):
            recipient_user_id = int(payload_parts[2].split("-")[1])
            operation_type = "gift"
            amount = plan.price
            logger.debug(f"Payment type: gift subscription to user {recipient_user_id}")
        else:
            await message.answer("⚠️ Ошибка в данных платежа. Попробуйте снова.")
            logger.error(f"Invalid payload format: {payload}")
            return

    async with await get_session() as session:
        try:
            result = await session.execute(
                db.select(PremiumSubscription).filter_by(user_id=user_id)
            )
            premium_user = result.scalar_one_or_none()

            # --- Тип: покупка подписки для себя ---
            if operation_type == "myself":
                logger.info(f"Processing self subscription purchase for user {user_id}")
                
                transaction_credit = Transaction(
                    user_id=user_id,
                    operation_type="credit",
                    amount=amount,
                    telegram_transaction_id=telegram_payment_id,
                )
                transaction_debit = Transaction(
                    user_id=user_id, operation_type="debit", amount=amount
                )
                session.add_all([transaction_credit, transaction_debit])
                await session.commit()

                result, msg = await create_subscription(
                    session=session,
                    user_id=user_id,
                    plan=plan,
                    premium_user=premium_user,
                )

                if msg:
                    return await message.answer(f"❌ <b>Произошла ошибка:</b>\n{msg}")

                text = (
                    "✅ <b>Подписка успешно оформлена!</b>\n\n"
                    f"🗓️ <b>Действует до:</b> <i>{result.expires_at.strftime('%d %B %Y, %H:%M')}</i>\n\n"
                    "Спасибо за поддержку проекта ❤️\n"
                    "Приятного использования 🚀"
                )
                
                logger.success(f"Self subscription activated for user {user_id}")

            # --- Тип: пополнение баланса ---
            elif operation_type == "replenish":
                logger.info(f"Processing balance replenishment for user {user_id}, amount: {amount}")
                
                transaction = Transaction(
                    user_id=user_id,
                    operation_type="credit",
                    amount=amount,
                    telegram_transaction_id=telegram_payment_id,
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
                
                logger.success(f"Balance replenished for user {user_id}, new balance: {premium_user.balance}")

            # --- Тип: подарок ---
            elif operation_type == "gift":
                logger.info(f"Processing gift subscription from user {user_id} to {recipient_user_id}")
                
                transaction_credit = Transaction(
                    user_id=user_id,
                    operation_type="credit",
                    amount=amount,
                    telegram_transaction_id=telegram_payment_id,
                )
                transaction_debit = Transaction(
                    user_id=user_id, operation_type="debit", amount=amount
                )
                session.add_all([transaction_credit, transaction_debit])
                await session.commit()

                result, msg = await create_subscription(
                    session=session,
                    user_id=recipient_user_id,
                    plan=plan,
                    premium_user=premium_user,
                )

                if msg:
                    await message.answer(f"❌ <b>Произошла ошибка:</b>\n{msg}")
                    return

                text = (
                    "🎉 <b>Вы оформили подарочную подписку!</b>\n\n"
                    f"@{data['username']} совсем скоро узнает о вашем сюрпризе 💌\n"
                    "Спасибо, что делитесь хорошим настроением ✨"
                )

                recipient_text = (
                    f"🎁 <b>Вам подарили подписку на {plan.text_name}!</b>\n\n"
                    f"👤 <b>Отправитель:</b> @{data['sender_username']}\n"
                    f"💬 <b>Сообщение:</b> <i>{data['description']}</i>\n\n"
                    f"🗓️ <b>Подписка активна до:</b> <i>{result.expires_at.strftime('%d %B %Y %H:%M')}</i>\n\n"
                    "✨ Наслаждайтесь всеми преимуществами подписки и удачного обучения!"
                )

                try:
                    chat = await bot.get_chat(recipient_user_id)
                    await bot.send_message(chat_id=chat.id, text=recipient_text)
                    logger.info(f"Gift notification sent to recipient {recipient_user_id}")
                except Exception as e:
                    logger.error(f"Failed to send gift notification to {recipient_user_id}: {e}")
                
                logger.success(f"Gift subscription sent from {user_id} to {recipient_user_id}")

            else:
                text = "⚠️ Неизвестный тип операции"
                await bot.refund_star_payment(
                    user_id=user_id, telegram_payment_charge_id=telegram_payment_id
                )
                logger.error(f"Unknown operation type for payment: {operation_type}")

            # Удаление основного сообщения
            try:
                await bot.delete_message(
                    chat_id=message.chat.id, message_id=data["main_message_id"]
                )
                logger.debug(f"Main message deleted for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to delete main message for user {user_id}: {e}")

            await message.answer(text, reply_markup=kb.back_to_menu)
            logger.success(f"Payment processed successfully for user {user_id}")

        except Exception as e:
            await session.rollback()
            logger.exception(f"Error processing payment for user {user_id}: {e}")
            await message.answer(
                "❌ Произошла ошибка при обработке платежа. Попробуйте позже"
            )

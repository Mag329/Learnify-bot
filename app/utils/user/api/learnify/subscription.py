from datetime import datetime, timedelta
import json
import logging
from sqlalchemy.orm import selectinload
from learnifyapi.client import LearnifyAPI
from learnifyapi.exceptions import APIError

import app.keyboards.user.keyboards as kb
from app.config.config import DEFAULT_LONG_CACHE_TTL, LEARNIFY_API_TOKEN
from app.utils.database import (AsyncSessionLocal, Gdz, PremiumSubscription, PremiumSubscriptionPlan,
                                User, db, Transaction)
from app.utils.user.decorators import handle_api_error
from app.utils.scheduler import scheduler
from app.utils.user.cache import redis_client


logger = logging.getLogger(__name__)


@handle_api_error()
async def get_user_info(user_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(User).filter_by(user_id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            return None
        
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                info = await api.get_user(user_id)
            except APIError as e:
                info = None
                
            return info
        
        
async def create_subscription(session, user_id, plan, premium_user):
    try:
        result = await session.execute(db.select(User).filter_by(user_id=user_id))
        user = result.scalar_one_or_none()
        if not user:
            logger.warning(f"[create_subscription] Пользователь {user_id} не найден в БД")
            return None, "Пользователь не найден"

        if not plan:
            logger.error(f"[create_subscription] Не передан тарифный план (user_id={user_id})")
            return None, "Не удалось определить тарифный план"

        if not premium_user:
            logger.warning(f"[create_subscription] PremiumSubscription отсутствует для {user_id}")
            return None, "Не найдена ваша подписка. Пожалуйста попробуйте позже"

        # Обновление подписки
        now = datetime.now()
        duration = timedelta(days=plan.duration)

        if premium_user.is_active and premium_user.expires_at:
            premium_user.expires_at += duration
            logger.info(f"[create_subscription] Продление подписки: +{plan.duration} дней для {user_id}, истекает {premium_user.expires_at}")
        else:
            premium_user.expires_at = now + duration
            premium_user.is_active = True
            logger.info(f"[create_subscription] Новая подписка активирована для {user_id}\nПлан: {plan.name}\nЦена: {plan.price}\nИстекает: {premium_user.expires_at}")

        premium_user.plan = plan.id
        await session.commit()

        # Взаимодействие с Learnify API
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                result = await api.create_user(
                    user_id=user_id,
                    expires_at=premium_user.expires_at
                )
            except APIError as e:
                if e.status_code == 400:
                    logger.debug(f"[create_subscription] Пользователь {user_id} уже существует в API — обновляем")
                    result = await api.update_user(
                        user_id=user_id,
                        expires_at=premium_user.expires_at,
                        is_active=True
                    )
                else:
                    logger.exception(f"[create_subscription] Ошибка API Learnify для user_id={user_id}: {e}")
                    return None, "Ошибка при активации подписки. Пожалуйста попробуйте позже"

        logger.info(f"[create_subscription] ✅ Подписка активирована: user_id={user_id}\nПлан: {plan.name}\nЦена: {plan.price}\nИстекает: {premium_user.expires_at}")
        return result, None

    except Exception as e:
        await session.rollback()
        logger.exception(f"[create_subscription] Непредвиденная ошибка для user_id={user_id}: {e}")
        return None, "Произошла ошибка при оформлении подписки. Пожалуйста попробуйте позже"
    
    
async def disable_subscription(user_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=user_id))
        user = result.scalar_one_or_none()

        if not user:
            return None
        
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                result = await api.deactivate_subscription(user_id)
            except APIError as e:
                result = None
                
            return True if result else False
    
    
@handle_api_error()
async def get_gdz_answers(user_id, homework, subject_id):
    if not subject_id:
        return None, None
    
    cache_key = f"auto_gdz:{user_id}:{homework.id}:{subject_id}"
    
    cached_full = await redis_client.get(cache_key)
    if cached_full:
        data = json.loads(cached_full)
        
        return data['main_text'], data['solutions']
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Gdz).filter_by(user_id=user_id, subject_id=subject_id))
        gdz_info = result.scalar_one_or_none()
        
    try:
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            gdz = await api.get_gdz_answers(
                user_id=user_id, 
                task_text=homework.task, 
                book_url=gdz_info.book_url, 
                search_by=gdz_info.search_by
            )
    except Exception as e:
        logger.exception(f"[get_gdz_answers] Ошибка Learnify API: {e}")
        return None, None
        
    main_text = (
        f'🧠 <b>Авто-гдз:</b>\n\n'
        f'📖 <b>Текст задания:</b>\n <code>{gdz.task_text}</code>\n\n'
    )
    
    title_map = {
        "pages": "Страница",
        "numbers": "Номер",
        "paragraphs": "Параграф"
    }
    title_label = title_map.get(gdz_info.search_by, "Задание")
    
    solutions = []
    for solution in getattr(gdz, "solutions", []):
        text = (
            f'📘 <b>{title_label} {solution.page_number}</b>\n\n'
            f'🔗 <a href="{solution.answer_url}">Ссылка на ГДЗ</a>\n\n'
        )
        solutions.append(
            {
                "text": text,
                "images": getattr(solution, "image_urls", [])
            }
        )
        
        if not solutions:
            logger.info(f"[get_gdz_answers] Решения не найдены (user_id={user_id}, subject_id={subject_id}, task='{homework.task}')")
            return (
                main_text + "⚠️ К сожалению, ответы по данному заданию не найдены 😔",
                []
            )
            
    cache_data = {
        "main_text": main_text,
        "solutions": solutions
    }
    ttl = DEFAULT_LONG_CACHE_TTL
    await redis_client.setex(cache_key, ttl, json.dumps(cache_data))
        
    return main_text, solutions


async def renew_subscription(user_id, bot):
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                db.select(PremiumSubscription)
                .options(selectinload(PremiumSubscription.plan_obj))
                .filter_by(user_id=user_id, is_active=True)
            )
            subscription = result.scalar_one_or_none()

            if not subscription:
                logger.warning(f"Подписка для user_id={user_id} не найдена или неактивна.")
                return

            plan = subscription.plan_obj
            if not plan:
                logger.error(f"Тарифный план для подписки user_id={user_id} отсутствует.")
                return

            if subscription.auto_renew and subscription.balance >= plan.price:
                result, error = await create_subscription(
                    session=session,
                    user_id=user_id,
                    plan=plan,
                    premium_user=subscription
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

                    logger.info(f"Подписка user_id={user_id} успешно продлена до {subscription.expires_at}.")

                    await schedule_renew_subscription(subscription.user_id, subscription.expires_at, bot)

                else:
                    text = (
                        "❌ <b>Ошибка при продлении подписки</b>\n\n"
                        f"<i>{error}</i>"
                    )
                    logger.error(f"Ошибка при продлении подписки user_id={user_id}: {error}")

            else:
                success = await disable_subscription(user_id)

                if success:
                    reason = (
                        "💰 Недостаточно средств для продления"
                        if subscription.auto_renew else
                        "⚙️ Автопродление отключено"
                    )
                    text = (
                        "❌ <b>Срок действия вашей подписки истек</b>\n\n"
                        f"{reason}\n"
                        f"💳 Баланс: {subscription.balance:.0f} ⭐️"
                    )
                    logger.info(f"Подписка user_id={user_id} деактивирована.")
                else:
                    text = (
                        "⚠️ <b>Ошибка при отключении подписки</b>\n\n"
                        "Не удалось деактивировать подписку"
                    )
                    logger.error(f"Ошибка: не удалось деактивировать подписку user_id={user_id}.")

            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=kb.delete_message
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

        except Exception as e:
            await session.rollback()
            logger.exception(f"Ошибка в renew_subscription для user_id={user_id}: {e}")


async def schedule_renew_subscription(user_id: int, expires_at: datetime, bot):
    job_id = f"renew_subscription_{user_id}"
    if expires_at < datetime.now():
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


async def delete_renew_subscription_task(user_id):
    job_id = f"renew_subscription_{user_id}"

    try:
        scheduler.remove_job(job_id)
    except:
        pass


async def restore_renew_subscription_jobs(bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(is_active=True)
        )
        users = result.scalars().all()
        for user in users:
            await schedule_renew_subscription(user.user_id, user.expires_at, bot)


async def successful_payment(user_id, message, telegram_payment_id, payload, data, bot):
    payload_parts = payload.split()
    
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
                user_id=user_id,
                telegram_payment_charge_id=telegram_payment_id
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
                    "✅ <b>Подписка успешно оформлена!</b>\n\n"
                    f"🗓️ <b>Действует до:</b> <i>{result.expires_at.strftime('%d %B %Y, %H:%M')}</i>\n\n"
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
                    await bot.send_message(
                        chat_id=chat.id, text=recipient_text
                    )
                except Exception as e:
                    pass
                    

            else:
                text = "⚠️ Неизвестный тип операции"
                await bot.refund_star_payment(
                    user_id=user_id,
                    telegram_payment_charge_id=telegram_payment_id
                )

            await bot.delete_message(chat_id=message.chat.id, message_id=data['main_message_id'])
            
            await message.answer(text, reply_markup=kb.back_to_menu)

        except Exception as e:
            await session.rollback()
            logger.exception(f"Ошибка обработки платежа: {e}")
            await message.answer("❌ Произошла ошибка при обработке платежа. Попробуйте позже")
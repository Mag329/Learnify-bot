from datetime import datetime, timedelta
import logging
from sqlalchemy.orm import selectinload
from learnifyapi.client import LearnifyAPI
from learnifyapi.exceptions import APIError

import app.keyboards.user.keyboards as kb
from app.config.config import LEARNIFY_API_TOKEN
from app.utils.database import (AsyncSessionLocal, Gdz, PremiumSubscription, PremiumSubscriptionPlan,
                                User, db)
from app.utils.user.decorators import handle_api_error
from app.utils.scheduler import scheduler


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
async def get_gdz_answers(user_id, task, subject_id):
    if not subject_id:
        return None, None
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Gdz).filter_by(user_id=user_id, subject_id=subject_id))
        gdz_info = result.scalar_one_or_none()
        
    try:
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            gdz = await api.get_gdz_answers(
                user_id=user_id, 
                task_text=task, 
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
        "numbers": "Задание",
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
            logger.info(f"[get_gdz_answers] Решения не найдены (user_id={user_id}, subject_id={subject_id}, task='{task}')")
            return (
                main_text + "⚠️ К сожалению, ответы по данному заданию не найдены 😔",
                []
            )
        
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

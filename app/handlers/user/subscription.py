from datetime import datetime, timedelta
import logging

from aiogram import F, Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, LabeledPrice, Message,
                           PreCheckoutQuery)

import app.keyboards.user.keyboards as kb
from app.states.user.states import ChooseAmountForPaymentState, ChooseUserForGiftState, SelectGdzUrlState
from app.utils.database import (AsyncSessionLocal, Gdz, PremiumSubscription,
                                PremiumSubscriptionPlan, Transaction, UserData, db)
from app.utils.user.api.learnify.subscription import (create_subscription,
                                                      get_user_info, successful_payment)
from app.utils.user.utils import get_student

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "subscription_page")
async def subscription_page_handler(callback: CallbackQuery, state: FSMContext):
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
    
    await state.update_data(main_message_id=callback.message.message_id)
        
    await callback.message.edit_text(text=text, reply_markup=await kb.subscription_keyboard(callback.from_user.id, subscription))
    

@router.callback_query(F.data == "get_subscription")
async def get_subscription_handler(callback: CallbackQuery):
    await callback.answer()
    await callback.message.edit_text('💎 <b>Learnify Premium</b>\n\nВыберите тарифный план', reply_markup=await kb.choose_subscription_plan('myself'))
    

@router.callback_query(F.data.startswith("subscription_plan_"))
async def subscription_plan_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = callback.data.split("_")
    type = data[3]
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscriptionPlan).filter_by(name=data[2]))
        plan = result.scalar_one_or_none()
        
        result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=callback.from_user.id))
        user = result.scalar_one_or_none()
        
        payload = f'{plan.id} for {type}'
        
        if user and user.balance < plan.price:
            await callback.message.answer_invoice(
                title="Learnify Premium",
                description=f"Learnify Premium на {plan.text_name}",
                prices=[LabeledPrice(label='Оплата подписки', amount=plan.price)],
                provider_token='',
                payload=payload,
                currency='XTR',
                reply_markup=await kb.buy_subscription_keyboard(plan.id, type)
            )
        else:
            user.balance -= plan.price
            await session.commit()
            
            state_data = await state.get_data()
            state_data['sender_username'] = callback.from_user.username
            
            await successful_payment(callback.from_user.id, callback.message, None, payload, state_data, bot)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment_handler(message: Message, state: FSMContext, bot: Bot):
    telegram_payment_id = message.successful_payment.telegram_payment_charge_id
    user_id = message.from_user.id
    data = await state.get_data()
    data['sender_username'] = message.from_user.username
    
    await successful_payment(user_id, message, telegram_payment_id, message.successful_payment.invoice_payload, data, bot)
            
            

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
            # if user.user_id == message.from_user.id:
            #     await message.answer(
            #         "❌ Вы не можете подарить подписку себе 😉",
            #         reply_markup=kb.back_to_menu
            #     )
            #     return
        
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
    

@router.callback_query(F.data == 'subscription_settings')
async def subscription_settings_handler(callback: CallbackQuery):
    text = '🎁 <b>Настройки подписки</b>'
    
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=await kb.subscription_settings(callback.from_user.id))
    
    
    
@router.callback_query(F.data == 'subscription_setting_auto_renew')
async def subscription_setting_auto_renew_handler(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=callback.from_user.id))
        user = result.scalar_one_or_none()
        if user:
            user.auto_renew = not user.auto_renew
            await session.commit()

            return await subscription_settings_handler(callback)
        

@router.callback_query(F.data == 'subscription_setting_auto_gdz')
async def subscription_setting_auto_gdz_handler(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Gdz).filter_by(user_id=callback.from_user.id))
        gdzs = result.scalars().all()
        
        text = (
            f"⚡ <b>Настройки авто-ГДЗ</b>\n\n"
            f"📚 Укажите ссылки на ГДЗ, которые хотите автоматизировать\n\n"
            f"🔗 <b>Текущие предметы:</b>\n"
            f"{'• ' + '\n• '.join([gdz.subject_name for gdz in gdzs]) if gdzs else '— пока ничего не добавлено —'}\n\n"
            f"👇 Выберите предмет ниже, чтобы изменить или добавить ссылку."
        )

        
        await callback.answer()
        await callback.message.edit_text(text=text, reply_markup=await kb.choice_subject(callback.from_user.id, 'auto_gdz'))

    
@router.callback_query(F.data.startswith('select_subject_auto_gdz_'))
async def select_subject_auto_gdz_handler(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split('_')[-1])
    
    text = (
        f"⚡ <b>Настройки авто-ГДЗ</b>\n\n"
    )
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Gdz).filter_by(user_id=callback.from_user.id, subject_id=subject_id))
        subject_gdz = result.scalar_one_or_none()
        if subject_gdz:
            search_by = {
                'pages': 'страницам',
                'numbers': 'номерам',
                'paragraphs': 'параграфам'
            }
            
            text  += (
                f"📚 <b>{subject_gdz.subject_name}</b>\n"
                f"🔗 <i>{subject_gdz.book_url}</i>\n"
                f'<b>Поиск по:</b> {search_by.get(subject_gdz.search_by, "неизвестному типу")}\n\n'
                f"👇 Выберите действие:"
            )
            
            await callback.answer()
            return await callback.message.edit_text(text=text, reply_markup=await kb.auto_gdz_settings(subject_gdz=subject_gdz))
        else:
            api, user = await get_student(callback.from_user.id)
            subjects = await api.get_subjects(
                student_id=user.student_id, profile_id=user.profile_id
            )
            subject_name = next(
                (subject.subject_name for subject in subjects.payload if subject.subject_id == subject_id),
                "Неизвестный предмет"
            )
            
            text += (
                f"📚 <b>{subject_name}</b>\n\n"
                f"🔗 Выберите ссылку для автоматизации ГДЗ (gdz.ru)\n\n"
            )
            await state.update_data(subject_id=subject_id)
            await state.update_data(subject_name=subject_name)
            await state.update_data(main_message_id=callback.message.message_id)
            await state.set_state(SelectGdzUrlState.link)
            
            await callback.answer()
            await callback.message.edit_text(text=text, reply_markup=kb.back_to_subscription_settings)
                
                
@router.message(F.text, StateFilter(SelectGdzUrlState.link))
async def select_gdz_url_handler(message: Message, state: FSMContext, bot: Bot):
    url = message.text.strip()
    if 'https://' not in url or 'gdz.ru' not in url:
        return await message.answer('❌ <b>Неверный формат ссылки</b>\nСсылка должна начинаться с <i>https://gdz.ru</i>', reply_markup=kb.back_to_subscription_settings)
    
    data = await state.get_data()
    await state.update_data(url=url)
    
    await message.delete()
    
    text = (
        f"⚡ <b>Настройки авто-ГДЗ</b>\n\n"
        f"📚 <b>{data['subject_name']}</b>\n"
        f"🔗 <i>{url}</i>\n\n"
        f"👇 Выберите тип поиска"
    )
    
    await state.set_state(None)
    
    await bot.edit_message_text(chat_id=message.from_user.id, message_id=data["main_message_id"], text=text,  reply_markup=kb.choose_search_by_auto_gdz)
    
@router.callback_query(F.data.startswith('auto_gdz_change_search_by_'))
async def auto_gdz_change_search_by_handler(callback: CallbackQuery, state: FSMContext):
    search_by = callback.data.split('_')[-1]
    if search_by not in ['pages', 'numbers', 'paragraphs']:
        return await callback.answer('❌ <b>Неверный формат данных</b>', show_alert=True)
    
    data = await state.get_data()
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Gdz).filter_by(user_id=callback.from_user.id, subject_id=data['subject_id']))
        subject_gdz = result.scalar_one_or_none()
        
        if subject_gdz:
            subject_gdz.book_url = data['url']
            subject_gdz.search_by = search_by
        else:
            subject_gdz = Gdz(
                user_id=callback.from_user.id,
                subject_id=data['subject_id'],
                subject_name=data['subject_name'],
                book_url=data['url'],
                search_by=search_by
            )
            session.add(subject_gdz)
        await session.commit()

        await callback.answer()
        return await subscription_setting_auto_gdz_handler(callback)
    

@router.callback_query(F.data.startswith('change_auto_gdz_'))
async def change_auto_gdz_handler(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split('_')[-1])
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Gdz).filter_by(user_id=callback.from_user.id, subject_id=subject_id))
        subject_gdz = result.scalar_one_or_none()
    
    text = (
        f"📚 <b>{subject_gdz.subject_name}</b>\n\n"
        f"🔗 Выберите ссылку для автоматизации ГДЗ\n\n"
    )
    await state.update_data(subject_id=subject_id)
    await state.update_data(subject_name=subject_gdz.subject_name)
    await state.update_data(main_message_id=callback.message.message_id)
    await state.set_state(SelectGdzUrlState.link)
    
    await callback.answer()
    await callback.message.edit_text(text=text, reply_markup=kb.back_to_subscription_settings)
                

@router.callback_query(F.data == 'back_to_auto_gdz')
async def back_to_auto_gdz_handler(callback: CallbackQuery, state: FSMContext):
    return await subscription_settings_handler(callback)
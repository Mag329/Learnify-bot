from datetime import datetime, timedelta
import logging
import os
import io

from aiogram import F, Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, LabeledPrice, Message,
                           PreCheckoutQuery, BufferedInputFile)

from app.config.config import MINIO_BUCKET_NAME, NO_PREMIUM_ERROR
import app.keyboards.user.keyboards as kb
from app.states.user.states import ChooseAmountForPaymentState, ChooseUserForGiftState, SelectBookState, SelectGdzUrlState
from app.utils.database import (AsyncSessionLocal, Gdz, PremiumSubscription,
                                PremiumSubscriptionPlan, StudentBook, Transaction, UserData, db)
from app.utils.misc import sanitize_filename
from app.utils.user.api.learnify.subscription import (create_subscription,
                                                      get_user_info, successful_payment)
from app.utils.user.utils import get_student
from app.minio import client as minio_client
from miniopy_async import Minio
from miniopy_async.error import S3Error

router = Router()
logger = logging.getLogger(__name__)



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
            f"👇 Выберите предмет ниже, чтобы изменить или добавить ссылку"
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
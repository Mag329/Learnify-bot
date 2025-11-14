from datetime import datetime, timedelta
import logging

from aiogram import F, Router, Bot
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (CallbackQuery, LabeledPrice, Message,
                           PreCheckoutQuery)
from aiogram.utils.media_group import MediaGroupBuilder

from app.config.config import NO_PREMIUM_ERROR
import app.keyboards.user.keyboards as kb
from app.states.user.states import ChooseAmountForPaymentState, ChooseUserForGiftState, QuickGdzState, SelectGdzUrlState
from app.utils.scheduler import scheduler
from app.utils.database import (AsyncSessionLocal, Gdz, PremiumSubscription,
                                PremiumSubscriptionPlan, Transaction, UserData, db)
from app.utils.misc import clear_state_if_still_waiting
from app.utils.user.api.learnify.subscription import (create_subscription, get_gdz_answers,
                                                      get_user_info, successful_payment)
from app.utils.user.utils import get_student

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("quick_gdz_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split("_")[-1])
    
    await callback.answer()
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=callback.from_user.id))
        premium_user = result.scalar_one_or_none()
        
        if not premium_user or not premium_user.is_active:
            await callback.message.answer(NO_PREMIUM_ERROR, reply_markup=kb.get_premium)
            return
    
        result = await session.execute(db.select(Gdz).filter_by(user_id=callback.from_user.id, subject_id=subject_id))
        gdz_info = result.scalar_one_or_none()
        
        if not gdz_info:
            text = (
                '❌ <b>Не указана ссылка для автоматизации ГДЗ</b>\n\n'
            )
            return await callback.message.answer(text, reply_markup=kb.set_auto_gdz_links)

        await callback.message.answer('⚡️ <b>Быстрое ГДЗ</b>', reply_markup=await kb.quick_gdz(subject_id, gdz_info.book_url, gdz_info.search_by))
        
        
@router.callback_query(F.data.startswith("choose_quick_gdz_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split("_")[-1])
    
    await callback.answer()
    await state.update_data(subject_id=subject_id)
    await state.set_state(QuickGdzState.number)
    
    job_id = f"clear_state_{callback.from_user.id}"
    
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)
    
    scheduler.add_job(
        clear_state_if_still_waiting,
        args=[state],
        trigger='date',
        run_date=datetime.now() + timedelta(minutes=2),
        id=job_id,
    )
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Gdz.search_by).filter_by(user_id=callback.from_user.id, subject_id=subject_id))
        search_by = result.scalar_one_or_none()
    
    search_by_list = {
        'pages': 'страницы',
        'numbers': 'задания',
        'paragraphs': 'параграфа'
    }
    
    await callback.message.edit_text(f'✏️ <b>Введите номер {search_by_list.get(search_by, 'задания')} для открытия ГДЗ</b>', reply_markup=kb.delete_message)
        

@router.message(StateFilter(QuickGdzState.number))
async def quick_gdz_number_handler(message: Message, state: FSMContext):
    data = await state.get_data()
    subject_id = data.get("subject_id")
    number = message.text
    await message.delete()
    
    if subject_id:
        if number.isdigit():
            await state.clear()
            
            temp_message = await message.answer(f'🔄 Загрузка...')
            
            text, solutions = await get_gdz_answers(user_id=message.from_user.id, subject_id=subject_id, number=number)
            
            await temp_message.delete()
            
            if not solutions:
                await message.answer('❌ <b>Ошибка</b>\n\nНе удалось получить ответы', reply_markup=kb.delete_message)
                return
            
            await message.answer(text, reply_markup=kb.delete_message, protect_content=True)
            
            def chunked(iterable, n):
                for i in range(0, len(iterable), n):
                    yield iterable[i:i + n]
            
            for num, solution in enumerate(solutions, 1):
                images = solution['images']
                text = solution['text']

                image_chunks = list(chunked(images, 10))
                total_parts = len(image_chunks)

                for i, image_chunk in enumerate(image_chunks, start=1):
                    if total_parts > 1:
                        caption = f"{num}. {text}\n🧩 Часть {i}/{total_parts}"
                    else:
                        caption = f"{num}. {text}"

                    media_group = MediaGroupBuilder(caption=caption)
                    for image in image_chunk:
                        media_group.add_photo(media=image)

                    await message.answer_media_group(
                        media=media_group.build(),
                        protect_content=True
                    )
            await message.answer(text='✅ <b>Выдача завершена</b>', reply_markup=kb.delete_message)
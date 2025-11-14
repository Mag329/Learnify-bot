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


@router.callback_query(F.data == 'student_book_settings')
async def student_book_settings_handler(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(StudentBook).filter_by(user_id=callback.from_user.id))
        books = result.scalars().all()
        
        text = (
            f"📖 <b>Настройка электронных учебников</b>\n\n"
            f"📚 Отправьте файлы учебников для быстрого доступа к ним\n\n"
            f"🔗 <b>Текущие предметы:</b>\n"
            f"{'• ' + '\n• '.join([book.subject_name for book in books]) if books else '— пока ничего не добавлено —'}\n\n"
            f"👇 Выберите предмет ниже, чтобы изменить или добавить файл учебника"
        )

        
        await callback.answer()
        await callback.message.edit_text(text=text, reply_markup=await kb.choice_subject(callback.from_user.id, 'book'))
        
        
@router.callback_query(F.data.startswith('select_subject_book_'))
async def select_subject_auto_gdz_handler(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split('_')[-1])
    
    await state.update_data(subject_id=subject_id)
    await state.set_state(SelectBookState.file)
    
    await callback.message.edit_text('📖 <b>Отправьте файл учебника</b>', reply_markup=kb.delete_message)
    
@router.message(F.document)
async def select_book_handler(message: Message, state, bot):
    data = await state.get_data()
    subject_id = data.get("subject_id")

    if not subject_id:
        await message.answer("❌ <b>Предмет не найден</b>\nПопробуйте выбрать его заново")
        return

    api, user = await get_student(message.from_user.id)
    subjects = await api.get_subjects(
        student_id=user.student_id, profile_id=user.profile_id
    )
    subject_name = next(
        (subject.subject_name for subject in subjects.payload if subject.subject_id == subject_id),
        "Неизвестный предмет"
    )

    _, ext = os.path.splitext(message.document.file_name)
    ext = ext.lower() or ".pdf"
    safe_name = sanitize_filename(subject_name)
    object_name = f"{message.from_user.id}/{subject_id}/{safe_name}{ext}"

    file = await bot.get_file(message.document.file_id)
    file_path = f"temp_{safe_name}{ext}"

    with open(file_path, "wb") as f:
        await bot.download_file(file.file_path, f)

    try:
        await minio_client.fput_object(MINIO_BUCKET_NAME, object_name, file_path)
        
        async with AsyncSessionLocal() as session:
            book = StudentBook(
                user_id=message.from_user.id,
                subject_id=subject_id,
                subject_name=subject_name,
                file=object_name
            )
            session.add(book)
            await session.commit()
        
        await message.answer("✅ Файл успешно загружен", reply_markup=kb.back_to_subscription_settings)

    except S3Error as e:
        await message.reply(f"❌ <b>Ошибка при загрузке файла</b>")
    finally:
        try:
            os.remove(file_path)
        except FileNotFoundError:
            pass
        
        
        
@router.callback_query(F.data.startswith('student_book_'))
async def student_book_handler(callback: CallbackQuery):
    subject_id = int(callback.data.split('_')[-1])
    
    await callback.answer()
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(PremiumSubscription).filter_by(user_id=callback.from_user.id))
        premium_user = result.scalar_one_or_none()
        
        if not premium_user or not premium_user.is_active:
            await callback.message.answer(NO_PREMIUM_ERROR, reply_markup=kb.get_premium)
            return
        
        result = await session.execute(
            db.select(StudentBook).filter_by(user_id=callback.from_user.id, subject_id=subject_id)
        )
        book = result.scalar_one_or_none()

        if not book:
            await callback.message.answer("❌ <b>Учебник не найден</b>", reply_markup=kb.set_student_book)
            return

        try:
            response = await minio_client.get_object(MINIO_BUCKET_NAME, book.file)
            data = await response.read()
            await response.release()
            
            file_name = book.file.split("/")[-1]

            file = BufferedInputFile(data, filename=file_name)
            await callback.message.answer_document(document=file)

        except S3Error as e:
            await callback.message.answer('❌ <b>Ошибка при получении файла</b>', reply_markup=kb.delete_message)
        except Exception as e:
            await callback.message.answer('⚠️ <b>Непредвиденная ошибка</b>', reply_markup=kb.delete_message)
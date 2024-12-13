from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from datetime import datetime, timedelta

from octodiary.apis import AsyncMobileAPI
from octodiary.urls import Systems

from config import START_MESSAGE, SUCCESSFUL_AUTH
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings
from app.utils.user.utils import get_student
from app.states.user.states import AuthState


router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(User).filter_by(user_id=message.from_user.id)
        )
        user = result.scalar_one_or_none()

        if user:
            result = await session.execute(
                db.select(Settings).filter_by(user_id=user.user_id)
            )
            settings = result.scalar_one_or_none()

            if not settings:
                settings = Settings(user_id=user.user_id)
                session.add(settings)

            await session.commit()
            
            api, student = await get_student(message.from_user.id)
            
            # new_token = await api.refresh_token(student.token)
            
            # user.token = new_token
            # await session.commit()
                    
            profile_id = (await api.get_users_profile_info())[0].id

            profile = await api.get_family_profile(profile_id=profile_id)
            
            user.profile_id = profile_id
            user.role = profile.profile.type
            user.person_id = profile.children[0].contingent_guid
            user.student_id = profile.children[0].id
            user.contract_id = profile.children[0].contract_id
            
            await session.commit()

            await message.answer(
                text=SUCCESSFUL_AUTH.format(profile.profile.last_name, profile.profile.first_name, profile.profile.middle_name),
                reply_markup=await kb.main(message.from_user.id),
            )
        else:
            await message.answer(
                text=START_MESSAGE,
                reply_markup=kb.start_command,
            )


@router.callback_query(F.data == "login")
async def login_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(text="⚡ Для доступа к информации <b>Московской электронной школы (МЭШ)</b> необходим логин от <b>mos.ru</b>.\n\nВы можете ввести:\n  - 👤 Логин\n  - ✉️ Email\n  - 📱 Номер телефон (в формате +7 без пробелов)\n\n⚠️ <b>Важно:</b> Для авторизации у Вас должен быть привязан номер телефона к аккаунту mos.ru\n\n⚠️ <b>Важно:</b> Мы не сохраняем данные вашей авторизации. Вся информация используется только для подключения к системе и предоставления данных.", reply_markup=None)

    await state.set_state(AuthState.main_message)
    await state.update_data(main_message=callback.message.message_id)

    await state.set_state(AuthState.login)


@router.message(F.text, AuthState.login)
async def login_handler(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(login=message.text)

    data = await state.get_data()

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=data["main_message"],
        text="🔒 Теперь введите ваш пароль от <b>mos.ru</b>.\n\n⚠️ <b>Важно:</b> Мы не сохраняем данные вашей авторизации. Пароль используется только для безопасного подключения к системе <b>Московской электронной школы (МЭШ)</b>",
        reply_markup=None,
    )
    await message.delete()

    await state.set_state(AuthState.password)


@router.message(F.text, AuthState.password)
async def password_handler(message: Message, state: FSMContext, bot: Bot):
    await state.update_data(password=message.text)

    data = await state.get_data()

    if data["login"] and data["password"]:
        await message.delete()

        try:
            api = AsyncMobileAPI(system=Systems.MES)
            sms_code = await api.login(username=data["login"], password=data["password"])
            await state.set_state(AuthState.sms_code_class)
            await state.update_data(sms_code_class=sms_code)
            
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=data["main_message"],
                text=f"📱 На ваш номер, привязанный к <b>mos.ru</b>, отправлено SMS с кодом подтверждения\nПожалуйста, введите код, чтобы завершить авторизацию",
                reply_markup=None,
            )

        except Exception as e:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=data["main_message"],
                text=f"❌ Ошибка авторизации",
                reply_markup=kb.start_command,
            )
            await state.clear()
            return
        
        
@router.message(F.text, AuthState.sms_code_class)
async def password_handler(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()

    if data["sms_code_class"]:
        await message.delete()
        await state.clear()

        sms_code_class = data["sms_code_class"]
        async with AsyncSessionLocal() as session:
            try:
                token = await sms_code_class.async_enter_code(message.text)
                if token:
                    result = await session.execute(
                        db.select(User).filter_by(user_id=message.from_user.id)
                    )
                    user = result.scalar_one_or_none()
                    if not user:
                        user = User(user_id=message.from_user.id, token=token)
                        session.add(user)
                        await session.commit()
                    
                    api, _ = await get_student(message.from_user.id)
                    
                    profile_id = (await api.get_users_profile_info())[0].id

                    profile = await api.get_family_profile(profile_id=profile_id)
                    user.profile_id = profile_id
                    user.role = profile.profile.type
                    user.person_id = profile.children[0].contingent_guid
                    user.student_id = profile.children[0].id
                    user.contract_id = profile.children[0].contract_id
                    
                    await session.commit()
                    
                    result = await session.execute(
                        db.select(Settings).filter_by(user_id=user.user_id)
                    )
                    settings = result.scalar_one_or_none()

                    if not settings:
                        settings = Settings(user_id=message.from_user.id)
                        session.add(settings)
                    
                    await session.commit()
                    
                    await message.answer(
                        text=SUCCESSFUL_AUTH.format(profile.profile.last_name, profile.profile.first_name, profile.profile.middle_name),
                        reply_markup=await kb.main(message.from_user.id),
                    )
                    
                else:
                    raise Exception("Invalid SMS code")

            except Exception as e:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=data["main_message"],
                    text=f"❌ Ошибка авторизации",
                    reply_markup=kb.start_command,
                )
                await state.clear()
                print(e)
                return


@router.callback_query(F.data == "delete_message")
async def delete_message_handler(callback: CallbackQuery, bot: Bot):
    await callback.answer()
    await callback.message.delete()


# @router.message(F.text == "📡 Состояние серверов МЭШ")
# async def schedule_handler(message: Message):
#     await message.answer(await api.server_status(message.from_user.id))



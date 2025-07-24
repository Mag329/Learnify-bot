import logging

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from octodiary.apis import AsyncMobileAPI
from octodiary.exceptions import APIError
from octodiary.urls import Systems

import app.keyboards.user.keyboards as kb
from app.config.config import AWAIT_RESPONSE_MESSAGE, START_MESSAGE, SUCCESSFUL_AUTH
from app.states.user.states import AuthState
from app.utils.database import AsyncSessionLocal, User, db
from app.utils.user.utils import (
    ensure_user_settings,
    get_error_message_by_status,
    get_student,
    get_web_api,
    save_profile_data,
)

router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(User).filter_by(user_id=message.from_user.id, active=True)
        )
        user = result.scalar_one_or_none()

        if user:
            await_message = await message.answer(AWAIT_RESPONSE_MESSAGE)

            await ensure_user_settings(session, message.from_user.id)

            api, _ = await get_student(message.from_user.id)

            profile = None
            try:
                profile_id = (await api.get_users_profile_info())[0].id

                profile = await api.get_family_profile(profile_id=profile_id)
                web_api, _ = await get_web_api(message.from_user.id, active=False)
                profiles = await web_api.get_student_profiles()

                user.profile_id = profile_id
                user.role = profile.profile.type
                user.person_id = profile.children[0].contingent_guid
                user.student_id = profile.children[0].id
                user.contract_id = profiles[0].ispp_account

                await session.commit()

            except APIError as e:
                logger.error(
                    f"APIError ({e.status_code}) for user {message.from_user.id}: {e}"
                )

                await message.edit_text(
                    text=get_error_message_by_status(e.status_code),
                    reply_markup=kb.start_command,
                )
                return

            except Exception as e:
                logger.exception(
                    f"Unhandled exception for user {message.from_user.id}: {e}"
                )

                # Редактирование сообщения для необработанных исключений
                await await_message.edit_text(
                    text="❌ Ошибка авторизации",
                    reply_markup=kb.start_command,
                )
                return

            await session.commit()

            await await_message.delete()

            await message.answer(
                text=SUCCESSFUL_AUTH.format(
                    profile.profile.last_name,
                    profile.profile.first_name,
                    profile.profile.middle_name,
                ),
                reply_markup=await kb.main(message.from_user.id),
            )

        else:
            await message.answer(
                text=START_MESSAGE,
                reply_markup=kb.start_command,
            )


@router.callback_query(F.data == "login")
async def login_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        text="⚡ Для доступа к информации <b>Московской электронной школы (МЭШ)</b> необходим логин от <b>mos.ru</b>.\n\nВы можете ввести:\n  - 👤 Логин\n  - ✉️ Email\n  - 📱 Номер телефон (в формате +7 без пробелов)\n\n⚠️ <b>Важно:</b> Для авторизации у Вас должен быть привязан номер телефона к аккаунту mos.ru\n\n⚠️ <b>Важно:</b> Мы не сохраняем данные вашей авторизации. Вся информация используется только для подключения к системе и предоставления данных.",
        reply_markup=None,
    )

    await state.set_state(AuthState.main_message)
    await state.update_data(main_message=callback.message.message_id)

    await state.set_state(AuthState.login)


@router.message(F.text, AuthState.login)
async def login_handler(message: Message, state: FSMContext, bot: Bot):
    """
    ### Обрабатывает ввод логина пользователя.

    Сохраняет логин и запрашивает ввод пароля

    Args:
        message (Message): Объект сообщения
        state (FSMContext): Контекст состояния FSM
        bot (Bot): Экземпляр Telegram-бота
    """

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
            sms_code = await api.login(
                username=data["login"], password=data["password"]
            )
            await state.set_state(AuthState.sms_code_class)
            await state.update_data(sms_code_class=sms_code)

            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=data["main_message"],
                text=f"📱 На ваш номер, привязанный к <b>mos.ru</b>, отправлено SMS с кодом подтверждения\nПожалуйста, введите код, чтобы завершить авторизацию",
                reply_markup=None,
            )

        except APIError as e:
            logger.error(
                f"APIError ({e.status_code}) for user {message.from_user.id}: {e}"
            )
            await state.clear()

            await message.edit_text(
                text=get_error_message_by_status(e.status_code),
                reply_markup=kb.start_command,
            )

        except Exception as e:
            logger.exception(
                f"Unhandled exception for user {message.from_user.id}: {e}"
            )
            await state.clear()

            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=data["main_message"],
                text="❌ Ошибка авторизации",
                reply_markup=kb.start_command,
            )


@router.message(F.text, AuthState.sms_code_class)
async def sms_handler(message: Message, state: FSMContext, bot: Bot):
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

                    else:
                        user.token = token
                        await session.commit()

                    api, _ = await get_student(message.from_user.id, active=False)

                    profile_info = await api.get_users_profile_info()

                    profile_id = profile_info[0].id

                    profile = await api.get_family_profile(profile_id=profile_id)
                    web_api, _ = await get_web_api(message.from_user.id, active=False)
                    profiles = await web_api.get_student_profiles()

                    user.profile_id = profile_id
                    user.role = profile.profile.type
                    user.person_id = profile.children[0].contingent_guid
                    user.student_id = profile.children[0].id
                    user.contract_id = profiles[0].ispp_account
                    user.active = True

                    await session.commit()

                    await ensure_user_settings(session, message.from_user.id)

                    await save_profile_data(
                        session, message.from_user.id, profile.profile
                    )

                    await message.answer(
                        text=SUCCESSFUL_AUTH.format(
                            profile.profile.last_name,
                            profile.profile.first_name,
                            profile.profile.middle_name,
                        ),
                        reply_markup=await kb.main(message.from_user.id),
                    )

                else:
                    await state.clear()
                    await message.answer(
                        "❌ Неверный код подтверждения. Попробуйте авторизоваться снова.",
                        reply_markup=kb.start_command,
                    )
                    return

            except APIError as e:
                logger.error(
                    f"APIError ({e.status_code}) for user {message.from_user.id}: {e}"
                )
                await state.clear()

                await message.edit_text(
                    text=get_error_message_by_status(e.status_code),
                    reply_markup=kb.start_command,
                )

            except Exception as e:
                logger.exception(
                    f"Unhandled exception for user {message.from_user.id}: {e}"
                )
                await state.clear()

                # Редактирование сообщения для необработанных исключений
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=data["main_message"],
                    text="❌ Ошибка авторизации",
                    reply_markup=kb.start_command,
                )


@router.callback_query(F.data == "exit_from_account")
async def exit_from_account(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(User).filter_by(user_id=callback.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            user.active = False
            await session.commit()

            await callback.answer()
            await callback.message.edit_text(
                "🚪 Вы вышли из аккаунта", reply_markup=kb.start_command
            )
        else:
            await callback.answer()
            await callback.message.edit_text(
                "❌ Ошибка выхода из аккаунта", reply_markup=kb.start_command
            )

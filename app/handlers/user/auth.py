import logging
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from octodiary.apis import AsyncMobileAPI
from octodiary.exceptions import APIError
from octodiary.urls import Systems
from datetime import datetime, timedelta
import aiohttp

import app.keyboards.user.keyboards as kb
from app.config.config import AWAIT_RESPONSE_MESSAGE, START_MESSAGE, SUCCESSFUL_AUTH, NO_SUBSCRIPTION_ERROR
from app.states.user.states import AuthState
from app.utils.database import AsyncSessionLocal, User, db, AuthData
from app.utils.user.utils import (
    ensure_user_settings,
    get_error_message_by_status,
    get_student,
    get_web_api,
    save_profile_data,
)
from app.utils.misc import check_subscription
from app.utils.user.api.mes.auth import get_token_expire_date, get_login_qr_code, check_qr_login, schedule_refresh
from app.utils.user.utils import deep_links


router = Router()
logger = logging.getLogger(__name__)


@router.message(CommandStart(deep_link=False))
@router.callback_query(F.data == 'check_subscription')
async def cmd_start(event: list[Message, CallbackQuery], bot: Bot, command: Optional[CommandStart] = None, state: Optional[FSMContext] = None):
    if isinstance(event, Message):
        user_id = event.from_user.id
        bot = event.bot
        message = event
        
        if command.args:
            return await deep_links(message, command.args, bot, state)
        
    elif isinstance(event, CallbackQuery):
        user_id = event.from_user.id
        bot = event.bot
        message = event.message
        await event.answer()
    else:
        return
    
    async with AsyncSessionLocal() as session:
        subscribe_status = await check_subscription(user_id, bot)
        if not subscribe_status:
            text= (
                "📢 <b>Для использования бота необходимо подписаться на наш канал!</b>\n\n"
                "ℹ️ Там мы публикуем только важные уведомления:\n"
                "🔄 Обновления\n"
                "⚙️ Информацию о работе бота\n\n"
                "🚫 Никакой рекламы — только полезная информация ✅"
            )
            await message.answer(text=text, reply_markup=kb.check_subscribe)
            return
        
        result = await session.execute(
            db.select(User).filter_by(user_id=user_id)
        )
        user = result.scalar_one_or_none()

        if user and user.active:
            await_message = await message.answer(AWAIT_RESPONSE_MESSAGE)

            await ensure_user_settings(session, user_id)

            try:
                api, _ = await get_student(user_id)

                profile = None
                
                profile_id = (await api.get_users_profile_info())[0].id

                profile = await api.get_family_profile(profile_id=profile_id)

                user.profile_id = profile_id
                user.role = profile.profile.type
                user.person_id = profile.children[0].contingent_guid
                user.student_id = profile.children[0].id
                
                clients = await api.get_clients(user.person_id)
                
                user.contract_id = clients.client_id.contract_id

                await session.commit()
                
                result = await session.execute(db.select(AuthData).filter_by(user_id=user_id, auth_method='password'))
                auth_data: AuthData = result.scalar_one_or_none()
                
                if auth_data:
                    token = await api.refresh_token(auth_data.token_for_refresh, auth_data.client_id, auth_data.client_secret)
                    if token:
                        user.token = token
                        auth_data.token_for_refresh = api.token_for_refresh
                        need_update_date = await get_token_expire_date(api.token)
                        auth_data.token_expired_at = need_update_date
                        await session.commit()

                        schedule_refresh(user.user_id, need_update_date)
                        
                await save_profile_data(
                    session, user_id, profile.profile
                )

            except APIError as e:
                logger.error(
                    f"APIError ({e.status_code}) for user {user_id}: {e}"
                )

                await await_message.edit_text(
                    text=get_error_message_by_status(e.status_code),
                    reply_markup=kb.start_command,
                )
                return

            except Exception as e:
                logger.exception(
                    f"Unhandled exception for user {user_id}: {e}"
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
                reply_markup=await kb.main(user_id),
            )

        else:
            if not user:
                user = User(user_id=user_id, active=False)
                session.add(user)
                await session.commit()
            
            await message.answer(
                text=START_MESSAGE,
                reply_markup=kb.start_command,
            )





@router.callback_query(F.data == 'choose_login')
async def choose_login_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    
    text = (
        "Выберите способ авторизации:\n\n"
        "👤 <b>1. По логину и паролю</b> (рекомендуется)\n"
        "  — Используйте логин и пароль от <a href='https://mos.ru'>mos.ru</a>\n"
        "  — 🔒 Сессия будет активна максимально долго\n\n"
        "🧾 <b>2. Через токен</b>\n"
        "  — Бот отправит ссылку для получения токена, скопируйте её и отправьте ему\n"
        "  — ⏳ Сессия будет активна до 10 дней\n\n"
        "📷 <b>3. Через QR-код</b>\n"
        "  — Отсканируйте QR-код в приложении <b>МЭШ</b>\n"
        "  — ⏳ Сессия ограничена сроком в 10 дней\n\n"
        "<i>⚠️ Рекомендуется использовать авторизацию через логин и пароль, чтобы не входить в аккаунт каждые 10 дней </i>"
    )
    
    await callback.answer()
    await callback.message.answer(text, reply_markup=kb.choice_auth_variant, disable_web_page_preview=True)


@router.callback_query(F.data == "auth_with_login")
async def login_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text(
        text="⚡ Для доступа к информации <b>Московской электронной школы (МЭШ)</b> необходим логин от <b>mos.ru</b>.\n\nВы можете ввести:\n  - 👤 Логин\n  - ✉️ Email\n  - 📱 Номер телефон (в формате +7 без пробелов)\n\n⚠️ <b>Важно:</b> Для авторизации у Вас должен быть привязан номер телефона к аккаунту mos.ru\n\n⚠️ <b>Важно:</b> Мы не сохраняем данные вашей авторизации. Вся информация используется только для подключения к системе и предоставления данных.",
        reply_markup=kb.back_to_choose_auth,
    )

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
        reply_markup=kb.back_to_choose_auth,
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
            await state.update_data(api_class=api)
            

            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=data["main_message"],
                text=f"📱 На ваш номер, привязанный к <b>mos.ru</b>, отправлено SMS с кодом подтверждения\nПожалуйста, введите код, чтобы завершить авторизацию",
                reply_markup=kb.back_to_choose_auth,
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
        api = data["api_class"]
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

                    profile_info = await api.get_users_profile_info()

                    profile_id = profile_info[0].id

                    profile = await api.get_family_profile(profile_id=profile_id)

                    user.profile_id = profile_id
                    user.role = profile.profile.type
                    user.person_id = profile.children[0].contingent_guid
                    user.student_id = profile.children[0].id
                    
                    clients = await api.get_clients(user.person_id)
                    
                    user.contract_id = clients.client_id.contract_id
                    user.active = True
                    
                    await session.commit()
                    
                    result = await session.execute(
                        db.select(AuthData).filter_by(user_id=message.from_user.id)
                    )
                    auth_data = result.scalar_one_or_none()
                    if not auth_data:
                        auth_data = AuthData(user_id=message.from_user.id)
                        session.add(auth_data)
                        await session.commit()     
                    
                    need_update_date = await get_token_expire_date(api.token)
                    
                    auth_data.auth_method = "password"
                    auth_data.token_expired_at = need_update_date
                    auth_data.token_for_refresh = api.token_for_refresh
                    auth_data.client_id = api.client_id
                    auth_data.client_secret = api.client_secret

                    await session.commit()
                    
                    schedule_refresh(user.user_id, need_update_date)

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
async def confirm_exit_from_account(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer('❗ Вы уверены, что хотите выйти из аккаунта?', reply_markup=kb.confirm_exit)


@router.callback_query(F.data == "confirm_exit_from_account")
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


@router.callback_query(F.data == "decline_exit_from_account")
async def decline_exit_from_account(callback: CallbackQuery):
    await callback.answer()
    await callback.message.delete()


@router.callback_query(F.data == "auth_with_token")
async def auth_by_token_callback_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AuthState.token)
    await state.update_data(main_message=callback.message.message_id)
    
    await callback.answer()
    text=(
        "🔐 <b>Авторизация по токену</b>\n\n"
        "1️⃣ Перейдите на страницу авторизации по кнопке ниже\n"
        "2️⃣ Войдите в аккаунт\n"
        "3️⃣ Вы будете перенаправлены на страницу с токеном\n"
        "4️⃣ Скопируйте токен, начинающийся с <code>eyJhb...</code>\n"
        "5️⃣ Скопируйте и отправьте этот токен боту\n\n"
        "<i>⏳ Обратите внимание: срок действия токена ограничен 10 днями. "
        "Для постоянной работы лучше использовать авторизацию по логину и паролю</i>"
    )
    
    await callback.message.answer(text, reply_markup=kb.token_auth)
    

@router.message(AuthState.token)
async def token_message_handler(message: Message, state: FSMContext, bot: Bot):
    token = message.text
    
    data = await state.get_data()
    if not data['main_message']:
        await message.answer(
            "❌ Ошибка авторизации",
            reply_markup=kb.start_command,
        )
    
    if not token.startswith('eyJhb'):
        return await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=data["main_message"],
                    text="❌ Токен должен начинаться с <code>eyJhb...</code>",
                    reply_markup=kb.token_auth,
                )
    
    await state.clear()
    
    token_expire_timestamp = await get_token_expire_date(token, 0)
    if token_expire_timestamp - datetime.now() < timedelta(hours=1):
        await message.answer(
            "❌ Токен истечёт меньше, чем через час\nПопробуйте авторизоваться заново через сайт <a href='https://mos.ru'>mos.ru</a>, или выберите другой способ авторизации",
            reply_markup=kb.start_command,
        )
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(User).filter_by(user_id=message.from_user.id))
        user = result.scalar_one_or_none()
        
        result = await session.execute(
            db.select(AuthData).filter_by(user_id=message.from_user.id)
        )
        auth_data = result.scalar_one_or_none()
        if not auth_data:
            auth_data = AuthData(user_id=message.from_user.id)
            session.add(auth_data)
            await session.commit()
            
        user.token = token
        auth_data.auth_method = "token"
        auth_data.token_expired_at = await get_token_expire_date(token)
        auth_data.token_for_refresh = None
        auth_data.client_id = None
        auth_data.client_secret = None
        
        await session.commit()
    
        api, _ = await get_student(message.from_user.id, active=False)
        
        profile_info = await api.get_users_profile_info()

        profile_id = profile_info[0].id

        profile = await api.get_family_profile(profile_id=profile_id)

        user.profile_id = profile_id
        user.role = profile.profile.type
        user.person_id = profile.children[0].contingent_guid
        user.student_id = profile.children[0].id
        
        clients = await api.get_clients(user.person_id)
        
        user.contract_id = clients.client_id.contract_id
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
        
@router.callback_query(F.data == "auth_with_qr")
async def auth_by_qr_callback_handler(callback: CallbackQuery, state: FSMContext):
    async with aiohttp.ClientSession() as http_session:
        status, qr_code = await get_login_qr_code(http_session)
        if not status:
            await callback.answer()
            return await callback.message.answer("❌ Ошибка генерации QR-кода. Пожалуйста, воспользуйтесь другим способом авторизации", reply_markup=kb.delete_message)
            
        await callback.answer()
        text = (
                "📲 Отсканируйте этот QR-код в мобильном приложении <b>МЭШ</b> для входа\n\n"
                "<i>⏳ Время ожидания: до 5 минут\n"
                "⏳ Обратите внимание: срок действия сессии ограничен 10 днями. "
                "Для постоянной работы лучше использовать авторизацию по логину и паролю</i>"
            )
        
        qr_code_message = await callback.message.answer_photo(qr_code, caption=text, reply_markup=kb.back_to_choose_auth)
        token = await check_qr_login(http_session)
        if not token:
            await qr_code_message.delete()
            await callback.message.answer("⏳ Время ожидания истекло. Попробуйте снова")
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(db.select(User).filter_by(user_id=callback.from_user.id))
            user = result.scalar_one_or_none()
            
            result = await session.execute(
                db.select(AuthData).filter_by(user_id=callback.from_user.id)
            )
            auth_data = result.scalar_one_or_none()
            if not auth_data:
                auth_data = AuthData(user_id=callback.from_user.id)
                session.add(auth_data)
                await session.commit()
                
            user.token = token
            auth_data.auth_method = "qr"
            auth_data.token_expired_at = await get_token_expire_date(token)
            auth_data.token_for_refresh = None
            auth_data.client_id = None
            auth_data.client_secret = None
            
            await session.commit()
            
            api, _ = await get_student(callback.from_user.id, active=False)
        
            profile_info = await api.get_users_profile_info()

            profile_id = profile_info[0].id

            profile = await api.get_family_profile(profile_id=profile_id)

            user.profile_id = profile_id
            user.role = profile.profile.type
            user.person_id = profile.children[0].contingent_guid
            user.student_id = profile.children[0].id
            
            clients = await api.get_clients(user.person_id)
            
            user.contract_id = clients.client_id.contract_id
            user.active = True
            
            await session.commit()
            
            await ensure_user_settings(session, callback.from_user.id)
            
            await save_profile_data(
                session, callback.from_user.id, profile.profile
            )
            
            await qr_code_message.delete()
            
            await callback.message.answer(
                text=SUCCESSFUL_AUTH.format(
                    profile.profile.last_name,
                    profile.profile.first_name,
                    profile.profile.middle_name,
                ),
                reply_markup=await kb.main(callback.from_user.id),
            )
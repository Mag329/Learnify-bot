from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable

from config import START_MESSAGE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User
from app.states.user.states import AuthState
from envparse import env


env.read_envfile()
        
        
class AllowedUsersMiddleware(BaseMiddleware):
    async def __call__(self,
                        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
                        event: TelegramObject,
                        data: Dict[str, Any]):
        if event.from_user.id in list(map(int, env.str("ALLOWED_USERS").split(","))):
            return await handler(event, data)
        
        

class CheckUserInDbMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):

        state = data.get("state")

        if (
            await state.get_state() != AuthState.login
            and await state.get_state() != AuthState.password
        ):
            bot = event.bot

            message = event

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    db.select(User).filter_by(user_id=message.from_user.id)
                )
                user = result.scalar_one_or_none()

                if user:
                    return await handler(event, data)
                else:
                    await bot.send_message(
                        message.chat.id,
                        START_MESSAGE,
                        reply_markup=kb.start_command,
                    )
                    return
        else:
            return await handler(event, data)

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import app.keyboards.user.keyboards as kb
from app.utils.user.api.mes.profile import get_profile
from app.utils.user.api.mes.rating import get_rating_rank_class
from app.utils.user.api.mes.visits import handle_visits_navigation

router = Router()


@router.message(F.text == "📋 Меню")
async def main_menu_handler(message: Message):
    await message.answer(
        "📋 Меню",
        reply_markup=await kb.menu(),
    )


@router.callback_query(
    F.data.in_({"visits", "visits_left", "visits_right", "visits_this_week"})
)
async def visits_navigation_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data_key = callback.data
    direction_map = {
        "visits": "today",
        "visits_left": "left",
        "visits_right": "right",
        "visits_this_week": "week",
    }

    direction = direction_map.get(data_key, "today")

    text, markup = await handle_visits_navigation(
        callback.from_user.id, state, direction
    )

    if text:
        await callback.message.edit_text(text=text, reply_markup=markup)
    else:
        await callback.message.edit_text(
            "📭 Посещений за выбранный период нет", reply_markup=markup
        )


@router.callback_query(F.data == "profile")
async def profile_callback_handler(callback: CallbackQuery):
    await callback.answer()

    text = await get_profile(callback.from_user.id)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.back_to_menu,
        )


@router.callback_query(F.data == "rating_rank_class")
async def rating_rank_class_callback_handler(callback: CallbackQuery):
    await callback.answer()

    text = await get_rating_rank_class(callback.from_user.id)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.back_to_menu,
        )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.clear()

    await callback.message.edit_text(
        text="📋 Меню",
        reply_markup=await kb.menu(),
    )

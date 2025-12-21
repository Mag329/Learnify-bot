from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import app.keyboards.user.keyboards as kb
from app.states.user.states import ResultsState
from app.utils.user.api.mes.results import (
    get_available_periods,
    get_results, 
    results_format, 
    detect_period_type,
    get_current_period,
    get_period_display_name
)
from app.utils.user.utils import get_student

router = Router()


@router.callback_query(F.data == "results")
async def results_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await callback.message.edit_text(text="⏳ Подведение итогов")

    api, user = await get_student(callback.from_user.id)
    
    data = await state.get_data()
    
    if "subjects" in data and "period_type" in data and "period_number" in data:
        period_type = data.get("period_type", "quarters")
        period_number = data.get("period_number", 1)
    else:
        period_type = await detect_period_type(api, user)
        period_number = await get_current_period(api, user, period_type)
    
    result_data = await get_results(callback.from_user.id, period_number=period_number, period_type=period_type)
    
    if result_data:
        await state.update_data(
            data=result_data,
            subject=0
        )

        text = await results_format(
            result_data, 
            "subjects", 
            0, 
            result_data.get("period_number", period_number),
            result_data.get("period_type", period_type)
        )
        
        if text:
            await callback.message.edit_text(
                text=text,
                reply_markup=await kb.get_results_keyboard(
                    result_data.get("period_type", period_type),
                    result_data.get("period_number", period_number)
                ),
            )


@router.callback_query(F.data.in_({"results_left", "results_right"}))
async def results_navigation_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    subjects = data.get("subjects", [])
    period_type = data.get("period_type", "четверти")
    period_number = data.get("period_number", 1)
    subject_index = data.get("subject", 0)

    if not subjects:
        return await callback.message.edit_text("❌ <b>Ошибка: нет доступных предметов</b>")

    direction = callback.data.split("_")[-1]  # "left" or "right"

    if direction == "right":
        subject_index = (subject_index + 1) % len(subjects)
    elif direction == "left":
        subject_index = (subject_index - 1) % len(subjects)

    await state.update_data(subject=subject_index)

    text = await results_format(
        data, "subjects", subject_index, period_number, period_type
    )
    
    if text:
        await callback.message.edit_text(
            text=text, 
            reply_markup=await kb.get_results_keyboard(period_type, period_number)
        )
    else:
        await callback.message.edit_text(
            "📭 Нет данных по предмету.", 
            reply_markup=await kb.get_results_keyboard(period_type, period_number)
        )


@router.callback_query(F.data == "subjects_results")
async def subjects_results_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    period_type = data.get("period_type", "quarters")
    period_number = data.get("period_number", 1)

    if "subjects" in data:
        await state.update_data(subject=0)

        text = await results_format(data, "subjects", 0, period_number, period_type)
        if text:
            await callback.message.edit_text(
                text=text,
                reply_markup=await kb.get_results_keyboard(period_type, period_number),
            )


@router.callback_query(F.data == "overall_results")
async def overall_results_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    period_type = data.get("period_type", "quarters")
    period_number = data.get("period_number", 1)
    if "subjects" in data:
        text = await results_format(data, "overall_results", period_number=period_number, period_type=period_type)
        if text:
            text_lines = text.split("\n")

            await state.update_data(line=1)
            await state.update_data(text=text_lines)

            await callback.message.edit_text(
                text=text_lines[0],
                reply_markup=await kb.get_overall_results_keyboard(period_type, period_number, has_more_lines=True),
            )


@router.callback_query(F.data == "next_line_results")
async def next_line_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    
    data = await state.get_data()
    line = data.get("line", 1)
    period_type = data.get("period_type", "quarters")
    period_number = data.get("period_number", 1)
    
    text_lines = data.get("text", [])

    while line < len(text_lines) and text_lines[line] == "":
        line += 1

    if line < len(text_lines):
        await state.update_data(line=line + 1)

        text = "\n".join(text_lines[: line + 1])

        await callback.message.edit_text(
            text=text,
            reply_markup=await kb.get_overall_results_keyboard(period_type, period_number, has_more_lines=True),
        )
    else:
        await callback.message.edit_text(
            text=callback.message.html_text,
            reply_markup=await kb.get_overall_results_keyboard(period_type, period_number, has_more_lines=False),
        )


@router.callback_query(F.data == "choose_period")
async def choose_period_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    period_type = data.get("period_type", "quarters")
    
    try:
        api, user = await get_student(callback.from_user.id)
        available_periods = await get_available_periods(api, user, period_type)
    except:
        available_periods = None
    
    keyboard = await kb.get_periods_keyboard(
        period_type, 
        available_periods, 
        user_id=callback.from_user.id
    )
    
    await callback.message.edit_text(
        text="Выберите период",
        reply_markup=keyboard,
    )


@router.callback_query(F.data.startswith("choose_period_"))
async def period_select_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    period_number = int(callback.data.split("_")[2])
    data = await state.get_data()
    period_type = data.get("period_type", "quarters")
    
    await state.update_data(period_number=period_number)
    
    period_display = await get_period_display_name(period_type, period_number)
    
    await callback.message.edit_text(
        text=f"Выбран {period_display}",
        reply_markup=kb.get_results,
    )


@router.callback_query(F.data == "refresh_results")
async def refresh_results_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("⏳ Обновление данных")
    
    data = await state.get_data()
    period_number = data.get("period_number", 1)
    period_type = data.get("period_type", "quarters")
    
    fresh_data = await get_results(callback.from_user.id, period_number, period_type, cache_bypass=True)
    
    if fresh_data:
        await state.update_data(data=fresh_data)
        await state.update_data(subject=0)
        
        text = await results_format(fresh_data, "subjects", 0, period_number, period_type)
        if text:
            await callback.message.edit_text(
                text=text,
                reply_markup=await kb.get_results_keyboard(period_type, period_number),
            )
    else:
        await callback.answer("❌ Не удалось обновить данные", show_alert=True)
        
        
@router.callback_query(F.data == "current_period_info")
async def current_period_info_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    period_type = data.get("period_type", "quarters")
    period_number = data.get("period_number", 1)
    
    period_names = {
        "quarters": {1: "1 четверть", 2: "2 четверть", 3: "3 четверть", 4: "4 четверть"},
        "half_years": {1: "1 полугодие", 2: "2 полугодие"},
        "trimesters": {1: "1 триместр", 2: "2 триместр", 3: "3 триместр"}
    }
    
    current_period_name = period_names.get(period_type, {}).get(period_number, f"Период {period_number}")
    
    await callback.answer(
        f"📊 Вы просматриваете результаты за {current_period_name}",
        show_alert=True
    )
    

@router.callback_query(F.data.startswith("period_not_available_"))
async def period_not_available_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    period_type = data.get("period_type", "quarters")
    period_number = data.get("period_number", 1)
    
    text = {
        "quarters": {1: "1 четверть ещё не началась", 2: "2 четверть ещё не началась", 3: "3 четверть ещё не началась", 4: "4 четверть ещё не началась"},
        "half_years": {1: "1 полугодие ещё не началось", 2: "2 полугодие ещё не началось"},
        "trimesters": {1: "1 триместр ещё не начался", 2: "2 триместр ещё не начался", 3: "3 триместр ещё не начался"}
    }
    
    await callback.answer(
        f'❌ {text.get(period_type, {}).get(period_number, f"Период {period_number} ещё не начался")}',
        show_alert=True
    )
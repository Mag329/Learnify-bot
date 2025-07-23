from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

import app.keyboards.user.keyboards as kb
from app.config.config import BASE_QUARTER
from app.states.user.states import ResultsState
from app.utils.user.api.mes.results import get_results, results_format

router = Router()


@router.callback_query(F.data == "results")
async def results_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await callback.message.edit_text(text="⏳ Подведение итогов")

    data = await state.get_data()

    quarter = data.get("quarter") if data.get("quarter") else BASE_QUARTER
    if not data.get("quarter"):
        await state.update_data(quarter=BASE_QUARTER)

    data = await get_results(callback.from_user.id, quarter)

    if data:
        await state.set_state(ResultsState.data)
        await state.update_data(data=data)
        await state.set_state(ResultsState.subject)
        await state.update_data(subject=0)

        text = await results_format(data, "subjects", 0, quarter)
        if text:
            await callback.message.edit_text(
                text=text,
                reply_markup=kb.results,
            )


@router.callback_query(F.data.in_({"results_left", "results_right"}))
async def results_navigation_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    subject_index = data.get("subject")
    subjects = data.get("subjects", [])

    if subject_index is None or not subjects:
        return await callback.message.edit_text("❌ Ошибка: нет доступных предметов.")

    direction = callback.data.split("_")[-1]  # "left" or "right"

    if direction == "right":
        subject_index = (subject_index + 1) % len(subjects)
    elif direction == "left":
        subject_index = (subject_index - 1) % len(subjects)

    await state.set_state(ResultsState.subject)
    await state.update_data(subject=subject_index)

    text = await results_format(
        data, "subjects", subject_index, quarter=data["quarter"]
    )
    if text:
        await callback.message.edit_text(text=text, reply_markup=kb.results)
    else:
        await callback.message.edit_text(
            "📭 Нет данных по предмету.", reply_markup=kb.results
        )


@router.callback_query(F.data == "subjects_results")
async def subjects_results_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if data is not []:
        await state.set_state(ResultsState.subject)
        await state.update_data(subject=0)

        text = await results_format(data, "subjects", 0)
        if text:
            await callback.message.edit_text(
                text=text,
                reply_markup=kb.results,
            )


@router.callback_query(F.data == "overall_results")
async def overall_results_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()
    if data is not []:
        text = await results_format(data, "overall_results", quarter=data["quarter"])
        if text:
            text = text.split("\n")

            await state.set_state(ResultsState.line)
            await state.update_data(line=1)
            await state.set_state(ResultsState.text)
            await state.update_data(text=text)

            await callback.message.edit_text(
                text=text[0],
                reply_markup=kb.overall_results_with_next_line,
            )


@router.callback_query(F.data == "next_line_results")
async def next_line_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    line = data.get("line", 1)

    # Получаем все строки текста
    text_lines = data.get("text", [])

    while line < len(text_lines) and text_lines[line] == "":
        line += 1

    if line < len(text_lines):
        # Отправляем следующую строку
        await state.update_data(line=line + 1)  # Обновляем индекс

        text = "\n".join(text_lines[: line + 1])

        await callback.message.edit_text(
            text=text,
            reply_markup=kb.overall_results_with_next_line,
        )
    else:
        await callback.message.edit_text(
            text=callback.message.html_text,
            reply_markup=kb.overall_results,
        )


@router.callback_query(F.data == "choose_quarter")
async def choose_quarter_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await callback.message.edit_text(
        text="Выберите четверть",
        reply_markup=kb.quarters,
    )


@router.callback_query(F.data.contains("choose_quarter_"))
async def quarter_1_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    quarter = callback.data.split("_")[2]

    await state.set_state(ResultsState.quarter)
    await state.update_data(quarter=quarter)

    await callback.message.edit_text(
        text=f"Выбрана {quarter} четверть",
        reply_markup=kb.get_results,
    )

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.states.user.states import SettingsEditStates
from app.utils.database import AsyncSessionLocal, SettingDefinition, Settings, db
from app.utils.user.utils import send_settings_editor

router = Router()


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    # text = f"⚙️ <b>Настройки</b>\n\n🤖 <b>Информация о боте</b>\n    - 📦 <b>Версия бота:</b> {BOT_VERSION}\n    - 👨‍💻 <b>Разработчик:</b> {DEVELOPER}\n    - 🌐 <b>Сайт разработчика:</b> {DEVELOPER_SITE}"

    # await message.answer(
    #     text,
    #     reply_markup=await kb.user_settings(message.from_user.id),
    #     disable_web_page_preview=True,
    # )
    await send_settings_editor(message, selected_index=0)


@router.callback_query(F.data.startswith(("nav_up_settings:", "nav_down_settings:")))
async def nav_settings_handler(callback: CallbackQuery):
    await callback.answer()

    action, index_str = callback.data.split(":")
    index = int(index_str)

    if action == "nav_up_settings":
        new_index = index - 1
    else:  # nav_down_settings
        new_index = index + 1

    await send_settings_editor(callback, selected_index=new_index)


@router.callback_query(F.data.startswith("edit_settings:"))
async def edit_setting(callback: CallbackQuery, state: FSMContext):
    try:
        _, index_str, key = callback.data.split(":")
        selected_index = int(index_str)
    except ValueError:
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with AsyncSessionLocal() as db_session:
        # Получаем определение настройки
        result = await db_session.execute(
            db.select(SettingDefinition).filter_by(key=key)
        )
        definition = result.scalar()

        if not definition:
            await callback.answer("Настройка не найдена", show_alert=True)
            return

        # Получаем текущие настройки сессии
        result = await db_session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings = result.scalar()

        if not settings:
            await callback.answer("Настройки не найдены", show_alert=True)
            return

        # Если тип bool — инвертируем и сохраняем
        if definition.type == "bool":
            current_value = getattr(settings, definition.key, False)
            setattr(settings, definition.key, not current_value)
            await db_session.commit()
            await send_settings_editor(callback, selected_index=selected_index)
        else:
            await callback.message.answer(
                f"Введите новое значение для: <b>{definition.label}</b>"
            )
            await state.update_data(
                setting_key=key,
                setting_type=definition.type,
                selected_index=selected_index,
            )
            await state.set_state(SettingsEditStates.waiting_for_value)


@router.message(SettingsEditStates.waiting_for_value)
async def process_new_setting_value(message: Message, state: FSMContext):
    data = await state.get_data()
    setting_key = data.get("setting_key")
    setting_type = data.get("setting_type")
    selected_index = data.get("selected_index")

    value = message.text.strip()

    # Попытка конвертировать значение согласно типу
    try:
        if setting_type == "int":
            value = int(value)
        elif setting_type == "float":
            value = float(value)
        # для string оставляем как есть
    except ValueError:
        await message.answer("❌ Неверный формат значения, попробуйте еще раз.")
        return

    async with AsyncSessionLocal() as db_session:
        result = await db_session.execute(
            db.select(Settings).filter_by(user_id=message.from_user.id)
        )
        settings = result.scalar()
        if not settings:
            await message.answer("⚠️ Настройки сессии не найдены.")
            await state.clear()
            return

        setattr(settings, setting_key, value)
        await db_session.commit()

    await message.answer("✅ Значение успешно обновлено!")
    await send_settings_editor(message, selected_index=selected_index)

    await state.clear()

# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.keyboards import user as kb
from app.states.user.states import SettingsEditStates
from app.utils.database import get_session, SettingDefinition, Settings, db
from app.utils.user.cache import clear_user_cache
from app.utils.user.utils import send_settings_editor

router = Router()


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    logger.info(f"User {message.from_user.id} opened settings menu")
    await send_settings_editor(message, selected_index=0, is_experimental=False)


@router.message(F.text == "🧪 Экспериментальные")
async def experimental_settings(message: Message):
    logger.info(f"User {message.from_user.id} opened experimental settings menu")
    await send_settings_editor(message, selected_index=0, is_experimental=True)


@router.callback_query(F.data.startswith(("nav_up_settings:", "nav_down_settings:")))
async def nav_settings_handler(callback: CallbackQuery):
    await callback.answer()

    action, index_str, settings_type = callback.data.split(":")
    index = int(index_str)
    is_experimental = settings_type == "experimental"
    
    logger.debug(f"User {callback.from_user.id} navigating settings: {action}, index={index}, experimental={is_experimental}")

    if action == "nav_up_settings":
        new_index = index - 1
    else:  # nav_down_settings
        new_index = index + 1

    await send_settings_editor(
        callback, selected_index=new_index, is_experimental=is_experimental
    )


@router.callback_query(F.data.startswith("edit_settings:"))
async def edit_setting(callback: CallbackQuery, state: FSMContext):
    try:
        _, index_str, key, settings_type = callback.data.split(":")
        selected_index = int(index_str)
        is_experimental = settings_type == "experimental"
    except ValueError:
        logger.error(f"Invalid edit_settings callback data: {callback.data}")
        await callback.answer("Некорректные данные", show_alert=True)
        return

    async with await get_session() as db_session:
        # Получаем определение настройки
        result = await db_session.execute(
            db.select(SettingDefinition).filter_by(key=key)
        )
        definition = result.scalar()

        if not definition:
            logger.warning(f"Setting definition not found for key: {key}")
            await callback.answer("Настройка не найдена", show_alert=True)
            return

        # Проверяем доступность экспериментальных функций
        if definition.experimental:
            result = await db_session.execute(
                db.select(Settings).filter_by(user_id=callback.from_user.id)
            )
            settings: Settings = result.scalar()
            if not settings or not settings.experimental_features:
                logger.warning(f"User {callback.from_user.id} attempted to edit experimental setting while experimental features disabled")
                await callback.answer(
                    "⚠️ Экспериментальные функции отключены", show_alert=True
                )
                return

        # Получаем текущие настройки сессии
        result = await db_session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings = result.scalar()

        if not settings:
            logger.warning(f"Settings not found for user {callback.from_user.id}")
            await callback.answer("Настройки не найдены", show_alert=True)
            return

        # Если тип bool — инвертируем и сохраняем
        if definition.type == "bool":
            current_value = getattr(settings, definition.key, False)
            new_value = not current_value
            setattr(settings, definition.key, new_value)
            await db_session.commit()
            
            logger.info(f"User {callback.from_user.id} toggled setting {key}: {current_value} -> {new_value}")
            
            await send_settings_editor(
                callback, selected_index=selected_index, is_experimental=is_experimental
            )
        else:
            logger.debug(f"User {callback.from_user.id} prompted to enter new value for {key} (type: {definition.type})")
            
            await callback.message.answer(
                f"Введите новое значение для: <b>{definition.label}</b>"
            )
            await state.update_data(
                setting_key=key,
                setting_type=definition.type,
                selected_index=selected_index,
                is_experimental=is_experimental,
            )
            await state.set_state(SettingsEditStates.waiting_for_value)


@router.message(SettingsEditStates.waiting_for_value)
async def process_new_setting_value(message: Message, state: FSMContext):
    data = await state.get_data()
    setting_key = data.get("setting_key")
    setting_type = data.get("setting_type")
    selected_index = data.get("selected_index")
    is_experimental = data.get("is_experimental", False)

    value = message.text.strip()
    original_value = value
    logger.debug(f"User {message.from_user.id} entering new value for {setting_key}: '{value}'")

    # Попытка конвертировать значение согласно типу
    try:
        if setting_type == "int":
            value = int(value)
        elif setting_type == "float":
            value = float(value)
        # для string оставляем как есть
    except ValueError:
        logger.warning(f"User {message.from_user.id} entered invalid {setting_type} value: '{original_value}'")
        await message.answer("❌ Неверный формат значения, попробуйте еще раз.")
        return

    async with await get_session() as db_session:
        result = await db_session.execute(
            db.select(Settings).filter_by(user_id=message.from_user.id)
        )
        settings = result.scalar()
        if not settings:
            logger.warning(f"Settings not found for user {message.from_user.id} while updating {setting_key}")
            await message.answer("⚠️ Настройки сессии не найдены.")
            await state.clear()
            return

        setattr(settings, setting_key, value)
        await db_session.commit()
        logger.info(f"User {message.from_user.id} updated setting {setting_key} to '{value}'")

    await message.answer("✅ Значение успешно обновлено!")
    await send_settings_editor(
        message, selected_index=selected_index, is_experimental=is_experimental
    )
    await state.clear()


@router.callback_query(F.data == "back_to_main_settings")
async def back_to_main_settings(callback: CallbackQuery):
    await callback.answer()
    logger.debug(f"User {callback.from_user.id} returning to main settings")
    await send_settings_editor(callback, selected_index=0, is_experimental=False)


@router.callback_query(F.data == "show_experimental_settings")
async def show_experimental_settings(callback: CallbackQuery):
    await callback.answer()
    logger.debug(f"User {callback.from_user.id} switching to experimental settings")
    await send_settings_editor(callback, selected_index=0, is_experimental=True)


@router.callback_query(F.data == "clear_cache")
async def clear_cache_handler(callback: CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    
    logger.info(f"User {user_id} clearing cache")
    
    num = await clear_user_cache(user_id)
    text = (
        "✅ <b>Кэш успешно очищен!</b>\n\n"
        f"🗑️ Удалено <i>{num}</i> сохранённых запросов"
    )
    
    logger.success(f"User {user_id} cleared cache, {num} items removed")
    await callback.message.answer(text, reply_markup=kb.delete_message)

# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class AuthState(StatesGroup):
    main_message = State()
    login = State()
    password = State()
    sms_code_class = State()
    token = State()


class ScheduleState(StatesGroup):
    date = State()


class HomeworkState(StatesGroup):
    date = State()


class MarkState(StatesGroup):
    date = State()


class VisitState(StatesGroup):
    date = State()


class ResultsState(StatesGroup):
    quarter = State()
    data = State()
    subject = State()
    line = State()
    text = State()


class SettingsEditStates(StatesGroup):
    waiting_for_value = State()


class ChooseAmountForPaymentState(StatesGroup):
    amount = State()
    main_message_id = State()


class ChooseUserForGiftState(StatesGroup):
    username = State()
    description = State()
    main_message_id = State()


class SelectGdzUrlState(StatesGroup):
    link = State()


class QuickGdzState(StatesGroup):
    number = State()


class SelectBookState(StatesGroup):
    file = State()

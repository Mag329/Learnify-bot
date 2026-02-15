# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class UpdateNotificationState(StatesGroup):
    text = State()
    confirm = State()

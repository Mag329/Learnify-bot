from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    WebAppInfo,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from datetime import datetime

from app.utils.database import AsyncSessionLocal, db, Settings
from app.utils.user.utils import get_student, get_emoji_subject


start_command = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Войти", callback_data="login")],
    ]
)

reauth = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🚪 Выйти из аккаунта", callback_data="exit_from_account"
            )
        ]
    ]
)

homework = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="homework_left"),
            InlineKeyboardButton(text="📅", callback_data="homework_today"),
            InlineKeyboardButton(text="➡️", callback_data="homework_right"),
        ],
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_homework"
            ),
        ],
    ]
)

subject_homework = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="subject_homework_left"),
            InlineKeyboardButton(text="📅", callback_data="subject_homework_today"),
            InlineKeyboardButton(text="➡️", callback_data="subject_homework_right"),
        ],
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_homework"
            ),
        ],
        [InlineKeyboardButton(text=f"↪️ Назад", callback_data=f"back_to_homework")],
    ]
)

schedule = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="schedule_left"),
            InlineKeyboardButton(text="📅", callback_data="schedule_today"),
            InlineKeyboardButton(text="➡️", callback_data="schedule_right"),
        ],
    ]
)

mark = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="mark_left"),
            InlineKeyboardButton(text="📅", callback_data="mark_today"),
            InlineKeyboardButton(text="➡️", callback_data="mark_right"),
        ],
        # [
        #     InlineKeyboardButton(text="📚 Выбрать предмет", callback_data="choose_subject_marks"),
        # ]
    ]
)

subject_marks = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="subject_marks_quarter_left"),
            InlineKeyboardButton(text="📅", callback_data="subject_marks_quarter_now"),
            InlineKeyboardButton(text="➡️", callback_data="subject_marks_quarter_right"),
        ],
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_marks"
            ),
        ],
        [InlineKeyboardButton(text=f"↪️ Назад", callback_data=f"back_to_marks")],
    ]
)

notifications_new = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔔 Новые", callback_data="notifications_new")]
    ]
)

notifications_all = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📩 Все", callback_data="notifications_all")]
    ]
)

menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📊 Посещаемость", callback_data="visits")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_rank_class")],
        [InlineKeyboardButton(text="🏆 Итоги", callback_data="results")],
    ]
)

visits = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="visits_left"),
            InlineKeyboardButton(text="📅", callback_data="visits_this_week"),
            InlineKeyboardButton(text="➡️", callback_data="visits_right"),
        ],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

results = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⬅️", callback_data="results_left"),
            InlineKeyboardButton(text="➡️", callback_data="results_right"),
        ],
        [InlineKeyboardButton(text="🏆 Общие итоги", callback_data="overall_results")],
        [
            InlineKeyboardButton(
                text="📅 Выбрать четверть", callback_data="choose_quarter"
            )
        ],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

overall_results_with_next_line = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⬇️", callback_data="next_line_results")],
        [
            InlineKeyboardButton(
                text="🏆 Итоги по предметам", callback_data="subjects_results"
            )
        ],
        [
            InlineKeyboardButton(
                text="📅 Выбрать четверть", callback_data="choose_quarter"
            )
        ],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

overall_results = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🏆 Итоги по предметам", callback_data="subjects_results"
            )
        ],
        [
            InlineKeyboardButton(
                text="📅 Выбрать четверть", callback_data="choose_quarter"
            )
        ],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

quarters = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣", callback_data="choose_quarter_1"),
            InlineKeyboardButton(text="2️⃣", callback_data="choose_quarter_2"),
        ],
        [InlineKeyboardButton(text="3️⃣", callback_data="choose_quarter_3")],
        # [InlineKeyboardButton(text="3️⃣", callback_data="choose_quarter_3"), InlineKeyboardButton(text="4️⃣", callback_data="choose_quarter_4")],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

get_results = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Подвести итоги", callback_data="results")],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

back_to_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")]
    ]
)

delete_message = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Закрыть", callback_data="delete_message")]
    ]
)


async def main(user_id):
    keyboard = ReplyKeyboardBuilder()

    keyboard.row(
        KeyboardButton(text="🔔 Уведомления"),
        KeyboardButton(text="📅 Расписание"),
    )
    keyboard.row(
        KeyboardButton(text="🎓 Оценки"),
        KeyboardButton(text="📚 Домашние задания"),
    )

    keyboard.row(
        KeyboardButton(text="📋 Меню"),
    )
    
    # keyboard.row(KeyboardButton(text="WebApp", web_app=WebAppInfo(url = 'https://genially-aesthetic-weasel.cloudpub.ru/')))

    keyboard.row(KeyboardButton(text="⚙️ Настройки"))

    return keyboard.as_markup(resize_keyboard=True)


async def user_settings(user_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings = result.scalar_one_or_none()

        keyboard = InlineKeyboardBuilder()

        keyboard.row(
            InlineKeyboardButton(
                text=f'Уведомления о новых оценках {"✅" if settings.enable_new_mark_notification else "❌"}',
                callback_data="enable_new_mark_notification_settings",
            )
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f'Уведомления о новых ДЗ {"✅" if settings.enable_homework_notification else "❌"}',
                callback_data="enable_homework_notification_settings",
            )
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f'Пропускать пустые дни (расписание) {"✅" if settings.skip_empty_days_schedule else "❌"}',
                callback_data="skip_empty_days_schedule_settings",
            )
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f'Пропускать пустые дни (ДЗ) {"✅" if settings.skip_empty_days_homeworks else "❌"}',
                callback_data="skip_empty_days_homeworks_settings",
            )
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f'Расписание на завтра{"✅" if settings.next_day_if_lessons_end_schedule else "❌"}',
                callback_data="next_day_if_lessons_end_schedule_settings",
            )
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f'ДЗ на завтра после уроков {"✅" if settings.next_day_if_lessons_end_homeworks else "❌"}',
                callback_data="next_day_if_lessons_end_homeworks_settings",
            )
        )

        # keyboard.row(
        #     InlineKeyboardButton(
        #         text=f'Экспериментальные функции {"✅" if settings.experimental_features else "❌"}',
        #         callback_data="experimental_features_settings",
        #     )
        # )

        keyboard.row(
            InlineKeyboardButton(
                text="🚪 Выйти из аккаунта", callback_data="exit_from_account"
            )
        )
        keyboard.row(
            InlineKeyboardButton(text="Закрыть", callback_data="delete_message")
        )

        return keyboard.as_markup()


async def choice_subject(user_id, for_):
    api, user = await get_student(user_id)

    subjects = await api.get_subjects(
        student_id=user.student_id, profile_id=user.profile_id
    )

    keyboard = InlineKeyboardBuilder()

    for subject in subjects.payload:
        keyboard.row(
            InlineKeyboardButton(
                text=f"{await get_emoji_subject(subject.subject_name)} {subject.subject_name}",
                callback_data=f"select_subject_{for_}_{subject.subject_id}",
            )
        )

    keyboard = keyboard.adjust(2)

    keyboard.row(InlineKeyboardButton(text=f"↪️ Назад", callback_data=f"back_to_{for_}"))

    return keyboard.as_markup()

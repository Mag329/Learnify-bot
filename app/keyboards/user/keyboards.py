from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from app.config.config import BUG_REPORT_URL, LEARNIFY_API_TOKEN, LEARNIFY_WEB
from app.utils.database import (
    get_session,
    PremiumSubscription,
    PremiumSubscriptionPlan,
    Settings,
    db,
)
from app.utils.user.api.mes.results import get_current_period
from app.utils.user.utils import get_emoji_subject, get_student

start_command = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🚪 Войти", callback_data="choose_login")],
    ]
)

choice_auth_variant = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🧑‍💻 Войти по логину", callback_data="auth_with_login"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔐 Войти по токену", callback_data="auth_with_token"
            )
        ],
        [
            InlineKeyboardButton(
                text="📷 Войти по QR-коду", callback_data="auth_with_qr"
            )
        ],
    ]
)

token_auth = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔑 Получить токен", url=f"{LEARNIFY_WEB}/api/v1/auth/method/token"
            )
        ],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="choose_login")],
    ]
)

back_to_choose_auth = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="choose_login")]
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

subject_homework_with_close = InlineKeyboardMarkup(
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
        [InlineKeyboardButton(text=f"Закрыть", callback_data=f"delete_message")],
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
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_marks"
            ),
        ],
    ]
)

subject_marks = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_marks"
            ),
        ],
        [InlineKeyboardButton(text=f"↪️ Назад", callback_data=f"back_to_marks")],
    ]
)

subject_marks_with_close = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📚 Выбрать предмет", callback_data="choose_subject_marks"
            ),
        ],
        [InlineKeyboardButton(text=f"Закрыть", callback_data=f"delete_message")],
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
            # InlineKeyboardButton(text="2️⃣", callback_data="choose_quarter_2"),
        ],
        # [
        #     InlineKeyboardButton(text="3️⃣", callback_data="choose_quarter_3"),
        #     InlineKeyboardButton(text="4️⃣", callback_data="choose_quarter_4"),
        # ],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

get_results = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Подвести итоги", callback_data="results")],
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")],
    ]
)

confirm_exit = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Да", callback_data="confirm_exit_from_account"
            ),
            InlineKeyboardButton(
                text="❌ Нет", callback_data="decline_exit_from_account"
            ),
        ],
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

link_to_channel = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔗 Перейти в канал", url="https://t.me/bot_learnify"
            )
        ]
    ]
)

check_subscribe = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🔗 Перейти в канал", url="https://t.me/bot_learnify"
            )
        ],
        [InlineKeyboardButton(text="🔎 Проверить", callback_data="check_subscription")],
    ]
)


get_premium = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="💎 Подробнее", callback_data="subscription_page")]
    ]
)

back_to_subscription_settings = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_auto_gdz")]
    ]
)

back_to_subscription_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="↪️ Назад", callback_data="subscription_page")]
    ]
)

choose_search_by_auto_gdz = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Страницы", callback_data=f"auto_gdz_change_search_by_pages"
            ),
            InlineKeyboardButton(
                text="Номера", callback_data=f"auto_gdz_change_search_by_numbers"
            ),
            InlineKeyboardButton(
                text="Параграфы", callback_data=f"auto_gdz_change_search_by_paragraphs"
            ),
        ]
    ]
)

set_auto_gdz_links = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✏️ Указать", callback_data="subscription_setting_auto_gdz"
            )
        ]
    ]
)


set_student_book = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Указать", callback_data="student_book_settings")]
    ]
)


confirm_pay = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="💳 Оплатить", callback_data="confirm_pay"),
            InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu"),
        ],
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

    keyboard.row(KeyboardButton(text="⚙️ Настройки"))

    return keyboard.as_markup(resize_keyboard=True)


async def menu():
    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text="📊 Посещаемость", callback_data="visits"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
    )
    keyboard.row(
        InlineKeyboardButton(text="📈 Рейтинг", callback_data="rating_rank_class"),
        InlineKeyboardButton(text="🏆 Итоги", callback_data="results"),
    )
    if LEARNIFY_API_TOKEN:
        keyboard.row(
            InlineKeyboardButton(text="💎 Подписка", callback_data="subscription_page")
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


async def auto_gdz_settings(subject_gdz):
    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="✏️ Изменить", callback_data=f"change_auto_gdz_{subject_gdz.subject_id}"
        ),
        InlineKeyboardButton(
            text="↪️ Назад", callback_data="subscription_setting_auto_gdz"
        ),
    )

    return keyboard.as_markup()


async def build_settings_nav_keyboard(
    user_id, definitions, selected_index, is_experimental=False
):
    async with await get_session() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings: Settings = result.scalar()

    selected_key = definitions[selected_index].key

    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(
            text="🔼",
            callback_data=f"nav_up_settings:{selected_index}:{'experimental' if is_experimental else 'main'}",
        ),
        InlineKeyboardButton(
            text="🔽",
            callback_data=f"nav_down_settings:{selected_index}:{'experimental' if is_experimental else 'main'}",
        ),
    )
    keyboard.row(
        InlineKeyboardButton(
            text="✏️ Изменить",
            callback_data=f"edit_settings:{selected_index}:{selected_key}:{'experimental' if is_experimental else 'main'}",
        )
    )

    if settings and settings.experimental_features:
        if is_experimental:
            keyboard.row(
                InlineKeyboardButton(
                    text="🔙 Назад", callback_data="back_to_main_settings"
                )
            )
        else:
            keyboard.row(
                InlineKeyboardButton(
                    text="🧪 Экспериментальные функции",
                    callback_data="show_experimental_settings",
                )
            )
            if settings.use_cache:
                keyboard.row(
                    InlineKeyboardButton(
                        text="📦 Очистить кэш", callback_data="clear_cache"
                    )
                )

    keyboard.row(InlineKeyboardButton(text="🤖 О боте", callback_data="about_bot"))
    keyboard.row(InlineKeyboardButton(text="🪲 Нашли ошибку?", url=BUG_REPORT_URL))

    keyboard.row(
        InlineKeyboardButton(
            text="🚪 Выйти из аккаунта", callback_data="exit_from_account"
        )
    )

    return keyboard.as_markup()


async def subscription_keyboard(user_id, subscription):
    async with await get_session() as session:

        keyboard = InlineKeyboardBuilder()

        if subscription and subscription.is_active:
            keyboard.row(
                InlineKeyboardButton(
                    text="💰 Пополнить",
                    callback_data="replenish_subscription",
                ),
                InlineKeyboardButton(
                    text="🎁 Подарить", callback_data="give_subscription"
                ),
            )
            keyboard.row(
                InlineKeyboardButton(
                    text="⚙️ Настройки", callback_data="subscription_settings"
                )
            )
        else:
            keyboard.row(
                InlineKeyboardButton(
                    text="✅ Оформить", callback_data="get_subscription"
                ),
                InlineKeyboardButton(
                    text="🎁 Подарить", callback_data="give_subscription"
                ),
            )

        keyboard.row(
            InlineKeyboardButton(
                text="📄 Договор оферты", callback_data="offer_contract"
            )
        )

        keyboard.row(InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu"))

        return keyboard.as_markup()


async def subscription_settings(user_id):
    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(user_id=user_id)
        )
        user = result.scalar_one_or_none()
        if user:
            keyboard = InlineKeyboardBuilder()
            keyboard.row(
                InlineKeyboardButton(
                    text=f"{'✅' if user.auto_renew else '❌'} Автопродление подписки",
                    callback_data="subscription_setting_auto_renew",
                )
            )
            keyboard.row(
                InlineKeyboardButton(
                    text="⚡️ Авто-ГДЗ", callback_data="subscription_setting_auto_gdz"
                )
            )
            keyboard.row(
                InlineKeyboardButton(
                    text="📖 Учебник", callback_data="student_book_settings"
                )
            )
            keyboard.row(
                InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu")
            )

            return keyboard.as_markup()


async def choose_subscription_plan(type):
    keyboard = InlineKeyboardBuilder()
    if LEARNIFY_API_TOKEN:
        async with await get_session() as session:
            result = await session.execute(
                db.select(PremiumSubscriptionPlan)
                .filter_by(show_in_menu=True)
                .order_by(PremiumSubscriptionPlan.ordering)
            )
            plans = result.scalars().all()

        for plan in plans:
            keyboard.button(
                text=f"{plan.title.capitalize()} ({plan.price} ⭐️)",
                callback_data=f"subscription_plan_{plan.name}_{type}",
            )

        # Автоматически формируем ряды по 2 кнопки
        keyboard.adjust(2)

        keyboard.row(InlineKeyboardButton(text="↪️ Назад", callback_data="back_to_menu"))

        return keyboard.as_markup()


async def buy_subscription_keyboard(
    price,
    for_,
):
    if LEARNIFY_API_TOKEN:
        keyboard = InlineKeyboardBuilder()
        if for_ == "myself":
            text = f"💳 Купить Premium за {price} ⭐️"
        elif for_ == "replenish":
            text = f"💳 Пополнить баланс на {price} ⭐️"
        else:
            text = f"🎁 Подарить Premium за {price} ⭐️"
        keyboard.row(
            InlineKeyboardButton(
                text=text,
                pay=True,
            )
        )


async def subject_menu(subject_id, date):
    keyboard = InlineKeyboardBuilder()

    if LEARNIFY_API_TOKEN:
        keyboard.row(
            InlineKeyboardButton(
                text="⚡️ Быстрое ГДЗ", callback_data=f"quick_gdz_{subject_id}"
            ),
            InlineKeyboardButton(
                text="🏠 ДЗ",
                callback_data=f"select_subject_homework_{subject_id}_{date.strftime("%d-%m-%Y")}_new",
            ),
        )
        keyboard.row(
            InlineKeyboardButton(
                text="🎯 Оценки", callback_data=f"select_subject_marks_{subject_id}_new"
            ),
            InlineKeyboardButton(
                text="📖 Учебник", callback_data=f"student_book_{subject_id}"
            ),
        )
    else:
        keyboard.row(
            InlineKeyboardButton(
                text="🏠 ДЗ",
                callback_data=f"select_subject_homework_{subject_id}_{date.strftime("%d-%m-%Y")}_new",
            ),
            InlineKeyboardButton(
                text="🎯 Оценки", callback_data=f"select_subject_marks_{subject_id}_new"
            ),
        )
    keyboard.row(InlineKeyboardButton(text="Закрыть", callback_data="delete_message"))

    return keyboard.as_markup()


async def quick_gdz(subject_id, link, search_by):
    search_by_dict = {"pages": "страницу", "numbers": "номер", "paragraphs": "параграф"}

    keyboard = InlineKeyboardBuilder()

    keyboard.row(
        InlineKeyboardButton(text="🔗 ГДЗ", url=link),
        InlineKeyboardButton(
            text=f"🔎 Выбрать {search_by_dict[search_by]}",
            callback_data=f"choose_quick_gdz_{subject_id}",
        ),
    )

    keyboard.row(InlineKeyboardButton(text="Закрыть", callback_data="delete_message"))

    return keyboard.as_markup()


async def get_periods_keyboard(period_type, available_periods=None):
    builder = InlineKeyboardBuilder()

    if period_type == "quarters":
        all_periods = [
            ("1️⃣", "1 четверть", 1),
            ("2️⃣", "2 четверть", 2),
            ("3️⃣", "3 четверть", 3),
            ("4️⃣", "4 четверть", 4),
        ]
    elif period_type == "half_years":
        all_periods = [("1️⃣", "1 полугодие", 1), ("2️⃣", "2 полугодие", 2)]
    elif period_type == "trimesters":
        all_periods = [
            ("1️⃣", "1 триместр", 1),
            ("2️⃣", "2 триместр", 2),
            ("3️⃣", "3 триместр", 3),
        ]
    else:
        all_periods = [("1️⃣", "Период 1", 1), ("2️⃣", "Период 2", 2)]

    if available_periods is None:
        available_periods = [p[2] for p in all_periods]

    for emoji, label, period_num in all_periods:
        if period_num in available_periods:
            callback_data = f"choose_period_{period_num}"
            text = f"{emoji} {label}"
            builder.button(text=text, callback_data=callback_data)
        else:
            builder.button(
                text=f"⚫️ {label}", callback_data=f"period_not_available_{period_num}"
            )

    builder.button(text="↪️ Назад", callback_data="back_to_menu")

    if len(all_periods) <= 2:
        builder.adjust(1, 1)
    elif len(all_periods) == 3:
        builder.adjust(2, 1, 1)
    elif len(all_periods) == 4:
        builder.adjust(2, 2, 1)

    return builder.as_markup()


async def get_results_keyboard(period_system, current_period):
    """Генерирует основную клавиатуру для результатов"""
    builder = InlineKeyboardBuilder()

    builder.button(text="⬅️", callback_data="results_left")
    builder.button(text="➡️", callback_data="results_right")

    period_names = {
        "quarters": "четверть",
        "half_years": "полугодие",
        "trimesters": "триместр",
    }

    period_label = period_names.get(period_system, "период")

    builder.button(text="♻️ Обновить", callback_data="refresh_results")
    builder.button(text="🏆 Общие итоги", callback_data="overall_results")

    # Информация о текущем периоде
    builder.button(text=f"📅 Сменить", callback_data="choose_period")
    builder.button(
        text=f"📍 {current_period} {period_label}", callback_data="current_period_info"
    )
    builder.button(text="↪️ Назад", callback_data="back_to_menu")

    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()


async def get_overall_results_keyboard(
    period_type, current_period, has_more_lines=False
):
    builder = InlineKeyboardBuilder()

    if has_more_lines:
        builder.button(text="⬇️ Показать еще", callback_data="next_line_results")

    builder.button(text="📚 Итоги по предметам", callback_data="subjects_results")

    period_names = {
        "quarters": "четверть",
        "half_years": "полугодие",
        "trimesters": "триместр",
    }

    period_label = period_names.get(period_type, "период")

    builder.button(text=f"📅 Сменить", callback_data="choose_period")
    builder.button(
        text=f"📍 {current_period} {period_label}", callback_data="current_period_info"
    )
    builder.button(text="♻️ Обновить", callback_data="refresh_results")
    builder.button(text="↪️ Назад", callback_data="back_to_menu")

    if has_more_lines:
        builder.adjust(1, 1, 2, 1)
    else:
        builder.adjust(1, 2, 1)

    return builder.as_markup()

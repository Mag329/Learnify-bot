from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config.config import LEARNIFY_API_TOKEN
from app.utils.database import (PremiumSubscription, PremiumSubscriptionPlan,
                                db, get_session)

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

from collections import defaultdict

from app.utils.user.decorators import handle_api_error, cache_text_only
from app.utils.user.utils import get_student


@handle_api_error()
@cache_text_only()
async def get_rating_rank_class(user_id):
    api, student = await get_student(user_id)
    profile = await api.get_family_profile(profile_id=student.profile_id)

    rating = await api.get_rating_rank_class(
        profile_id=student.profile_id,
        person_id=student.person_id,
        class_unit_id=profile.children[0].class_unit_id,
    )

    text = ""

    grouped = defaultdict(list)
    for user in rating:
        grouped[user.rank.average_mark_five].append(user)

    place_in_class = 0

    for avg_mark, users in sorted(grouped.items(), reverse=True):
        count = len(users)
        filled = int((avg_mark / 5) * 20)
        bar = f'{"▇" * filled}{"▁" * (20 - filled)}'

        # Форматирование с фиксированными длинами
        place = str(users[0].rank.rank_place).rjust(2)
        avg_mark_str = f"{avg_mark:.2f}".rjust(5)
        count_str = str(count)

        if users[0].person_id == student.person_id:
            place_in_class = users[0].rank.rank_place
            text += f"{place} {bar} {avg_mark_str} ({count_str} чел.) 🌟\n"
        else:
            text += f"{place} {bar} {avg_mark_str} ({count_str} чел.)\n"

    return f"📈 Рейтинг по классу (Ваше место: {place_in_class})\n<pre>{text}</pre>"

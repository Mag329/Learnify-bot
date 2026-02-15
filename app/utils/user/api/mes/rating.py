from collections import defaultdict
from loguru import logger

from app.utils.user.decorators import cache_text_only, handle_api_error
from app.utils.user.utils import get_student


@handle_api_error()
@cache_text_only()
async def get_rating_rank_class(user_id):
    logger.info(f"Getting class rating for user {user_id}")
    
    api, student = await get_student(user_id)
    if not api or not student:
        logger.error(f"Failed to get student data for user {user_id}")
        return "❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика"
    
    logger.debug(f"Fetching family profile for user {user_id}")
    profile = await api.get_family_profile(profile_id=student.profile_id)
    
    if not profile or not profile.children:
        logger.error(f"No children data in profile for user {user_id}")
        return "❌ <b>Ошибка</b>\n\nНе удалось получить данные профиля"

    class_unit_id = profile.children[0].class_unit_id
    logger.debug(f"Class unit ID: {class_unit_id}")

    logger.debug(f"Fetching rating rank class for user {user_id}")
    rating = await api.get_rating_rank_class(
        profile_id=student.profile_id,
        person_id=student.person_id,
        class_unit_id=class_unit_id,
    )
    
    if not rating:
        logger.warning(f"No rating data found for user {user_id}")
        return "❌ <b>Рейтинг недоступен</b>\n\nДанные о рейтинге класса отсутствуют"

    text = ""
    grouped = defaultdict(list)
    
    for user in rating:
        grouped[user.rank.average_mark_five].append(user)

    logger.debug(f"Grouped by average mark: {len(grouped)} groups")
    
    place_in_class = 0
    total_students = len(rating)
    logger.debug(f"Total students in class: {total_students}")

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
            logger.debug(f"Current user's position: place {place_in_class}, avg mark {avg_mark:.2f}")
        else:
            text += f"{place} {bar} {avg_mark_str} ({count_str} чел.)\n"

    result = f"📈 Рейтинг по классу (Ваше место: {place_in_class} из {total_students})\n<pre>{text}</pre>"        
    logger.success(f"Class rating generated for user {user_id}, place: {place_in_class}/{total_students}")
    return result
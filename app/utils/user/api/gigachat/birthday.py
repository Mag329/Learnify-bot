import logging
import re

from envparse import Env
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

env = Env()
env.read_envfile()

logger = logging.getLogger(__name__)

TOKEN = env.str("GIGACHAT_TOKEN")

ALLOWED_HTML_TAGS = {"b", "i", "u", "code", "pre", "a"}


async def sanitize_html(text: str) -> str:
    """Удаляет неподдерживаемые HTML-теги"""
    # Удаляем <br>, <div>, и т.д.
    text = re.sub(r"<(?!\/?(b|i|u|code|pre|a)\b)[^>]*>", "", text)
    return text


async def birthday_greeting(name):
    payload = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content="Ты — дружелюбный, немного ироничный бот по имени Learnify, который помогает школьникам справляться с учёбой: оценками, домашкой и расписанием. Сейчас тебе нужно поздравить школьника с днём рождения.",
            ),
            Messages(
                role=MessagesRole.USER,
                content=(
                    "Составь короткое поздравление с днём рождения для школьника от имени команды Learnify. "
                    "Поздравление должно быть в формате HTML для парсинга Telegram, использовать эмодзи, и быть структурированным (каждое предложение с новой строки). "
                    "Ключевые слова можно выделять тегами <b>жирного</b> и <i>курсива</i>."
                    f"Имя ученика: {name}. "
                    "Но не добавляй имя в начале, как обращение, и не подписывайся в конце."
                    "Можно вставить имя внутри поздравления, если это уместно. "
                    "Только 3–5 предложений поздравления, без заголовков, приветствий и подписей."
                ),
            ),
        ],
        temperature=0.5,
        max_tokens=200,
    )

    try:
        with GigaChat(credentials=TOKEN, verify_ssl_certs=False) as giga:
            response = giga.chat(payload)

        logger.info(f"GigaChat raw response: {response}")

        text = response.choices[0].message.content.strip()

        clean_text = await sanitize_html(text)

        logger.info(f"Final cleaned text: {clean_text}")

        return clean_text

    except Exception as e:
        logger.exception(f"Failed to get birthday greeting from GigaChat: {e}")
        return None

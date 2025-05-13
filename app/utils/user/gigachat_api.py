from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from envparse import Env


env = Env()
env.read_envfile()

TOKEN = env.str("GIGACHAT_TOKEN")


async def birthday_greeting(name):

    payload = Chat(
        messages=[
            Messages(
                role=MessagesRole.SYSTEM,
                content="Ты — дружелюбный, немного ироничный бот по имени Learnify, который помогает школьникам справляться с учёбой: оценками, домашкой и расписанием. Сейчас тебе нужно поздравить школьника с днём рождения."
            ),
            Messages(
                role=MessagesRole.USER,
                content=(
                    "Составь короткое поздравление с днём рождения для школьника от имени команды Learnify. "
                    "Поздравление должно быть в формате HTML, использовать эмодзи, и быть структурированным (каждое предложение с новой строки). "
                    "Ключевые слова можно выделять тегами <b>жирного</b> и <i>курсива</i>. "
                    f"Имя ученика: {name}. "
                    "Но не добавляй имя в начале, как обращение, и не подписывайся в конце. "
                    "Можно вставить имя внутри поздравления, если это уместно. "
                    "Только 3–5 предложений поздравления, без заголовков, приветствий и подписей."
                )
            )
        ],
        temperature=0.5,
        max_tokens=200,
    )

    with GigaChat(credentials=TOKEN, verify_ssl_certs=False) as giga:
        try:
            response = giga.chat(payload)
            return response.choices[0].message.content
        except Exception as e:
            return None
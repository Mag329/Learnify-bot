BOT_VERSION = "1.8.1 (prerelease)"


# Bot info
DEVELOPER = "@Mag329"
DEVELOPER_SITE = "https://mag329.site"


# Other
BASE_QUARTER = 4
LOG_FILE = "logs/bot.log"


# MESSAGES
AWAIT_RESPONSE_MESSAGE = "⌛ <b>Ожидание ответа серверов МЭШ</b>"
START_MESSAGE = "👋 Привет! Я бот для работы с <b>Московской электронной школой (МЭШ)</b>\nЯ помогу тебе следить за <b>расписанием</b>, <b>оценками</b>, <b>домашними заданиями</b> и т.д.\n\nДля начала нужно авторизоваться, нажми кнопку под сообщением"
ERROR_MESSAGE = "❌ <b>Произошла ошибка</b>"
ERROR_403_MESSAGE = "❌ <b>Произошла ошибка</b>\nВремя действия токена доступа истекло, пожалуйста авторизуйтесь заново"
ERROR_408_MESSAGE = (
    "❌ <b>Произошла ошибка</b>\nПревышено время ожидания ответа сервера МЭШ"
)
ERROR_500_MESSAGE = "❌ <b>Произошла ошибка</b>\nВнутренняя ошибка сервера МЭШ"
SUCCESSFUL_AUTH = "✅ <b>Успешная авторизация</b>\n\nВы вошли как <i>{0} {1} {2}</i>"
UPDATE_NOTIFICATION_HEADER = "🚀 <b>Обновление</b>\n\n"
UPDATE_NOTIFICATION_FOOTER = f"\n\n\n<i>Версия бота:</i> {BOT_VERSION}"


# LOAD
from envparse import Env

env = Env()
env.read_envfile()

LOGSTASH_HOST = env.str("LOGSTASH_HOST")
LOGSTASH_PORT = env.int("LOGSTASH_PORT")
LEARNIFY_WEB = env.str('LEARNIFY_WEB')

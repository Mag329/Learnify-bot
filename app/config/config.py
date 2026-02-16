# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

BOT_VERSION = "1.9.1.4"


# Bot info
DEVELOPER = "@Mag329"
DEVELOPER_SITE = "https://mag329.tech"

BUG_REPORT_URL = "https://forms.gle/X55ZfURLosXAG5Yw5"


# Other
BASE_QUARTER = 1


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
NO_SUBSCRIPTION_TO_CHANNEL_ERROR = "📢 <b>Для использования бота необходимо подписаться на наш канал!</b>\n\nПосле подписки повторите команду"
NO_PREMIUM_ERROR = f"❌ <b>Ошибка</b>\n\nУ вас нет подписки <b>Learnify Premium</b> для доступа к этой функции"


# LOAD
from envparse import Env

env = Env()
env.read_envfile()

LOGSTASH_HOST = env.str("LOGSTASH_HOST")
LOGSTASH_PORT = env.int("LOGSTASH_PORT")
LEARNIFY_WEB = env.str("LEARNIFY_WEB")
LEARNIFY_API_TOKEN = env.str("LEARNIFY_API_TOKEN", default=None)

DEFAULT_SHORT_CACHE_TTL = env.int("DEFAULT_SHORT_CACHE_TTL")
DEFAULT_MEDIUM_CACHE_TTL = env.int("DEFAULT_MEDIUM_CACHE_TTL")
DEFAULT_LONG_CACHE_TTL = env.int("DEFAULT_LONG_CACHE_TTL")
DEFAULT_CACHE_TTL = env.int("DEFAULT_CACHE_TTL")

CHANNEL_ID = env.int("CHANNEL_ID", default=None)
DEV = env.bool("DEV")


BOT_USERNAME = None
ALLOWED_USERS = list(map(int, env.list("ALLOWED_USERS", default=[])))
ONLY_ALLOWED_USERS = env.bool("ONLY_ALLOWED_USERS", default=False)
REDIS_HOST = env.str("REDIS_HOST", default="localhost")
REDIS_PORT = env.int("REDIS_INTERNAL_PORT", default=6379)

MINIO_ROOT_USER = env.str("MINIO_ROOT_USER", default="minioadmin")
MINIO_ROOT_PASSWORD = env.str("MINIO_ROOT_PASSWORD", default="minioadmin")
MINIO_HOST = env.str("MINIO_HOST", default="localhost")
MINIO_INTERNAL_PORT = env.int("MINIO_INTERNAL_PORT", default=9000)
MINIO_BUCKET_NAME = env.str("MINIO_BUCKET_NAME", default="learnify_bot")

TG_PROXY = env.str("TG_PROXY", default=None)

# Logs
LOG_FILE = env.str("LOG_FILE", default="logs/bot.log")
ERRORS_LOG_FILE = env.str("ERRORS_LOG_FILE", default="logs/errors.log")
LOG_LEVEL = env.str("LOG_LEVEL", default="INFO")
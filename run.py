import asyncio
import logging
import coloredlogs
import os

from app import main
from app.utils.database import run_migrations
from config import LOG_FILE


# Проверяем наличие директории для логов
log_dir = os.path.dirname(LOG_FILE)  # Получаем путь к папке

if log_dir and not os.path.exists(log_dir):  # Если путь не пустой и папки нет
    os.makedirs(log_dir, exist_ok=True)  # Создаем папку

if __name__ == "__main__":
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    log_format = "%(asctime)s %(name)s[%(process)d] %(levelname)s: %(message)s"

    # Set up colored logging
    coloredlogs.install(level="INFO", fmt=log_format)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format))

    logger.addHandler(file_handler)

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(main())  # Создаем задачу в текущем цикле
        else:
            asyncio.run(main())  #
    except KeyboardInterrupt:
        print("Exit")

import asyncio
import logging
import coloredlogs

from app import main
from app.utils.database import run_migrations

if __name__ == "__main__":
    # Set up colored logging
    coloredlogs.install(
        level="INFO", fmt="%(asctime)s %(name)s[%(process)d] %(levelname)s: %(message)s"
    )

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(main())  # Создаем задачу в текущем цикле
        else:
            asyncio.run(main())  #
    except KeyboardInterrupt:
        print("Exit")

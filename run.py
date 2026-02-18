# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import asyncio
import os
import sys
import socket
from datetime import datetime
import json

from loguru import logger

from app import main
from app.config.config import LOG_FILE, ERRORS_LOG_FILE, LOG_LEVEL, LOGSTASH_HOST, LOGSTASH_PORT, BOT_VERSION

log_dir = os.path.dirname(LOG_FILE)

if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

def logstash_sink(message):
    try:
        record = message.record
        
        # Формируем документ для Logstash
        log_entry = {
            "event_type": "log", 
            "@timestamp": record["time"].isoformat(),
            "level": record["level"].name,
            "logger": record["name"],
            "module": record["name"],
            "function": record["function"],
            "line": record["line"],
            "message": record["message"],
            "process_id": record["process"].id,
            "thread_id": record["thread"].id,
            "bot_version": BOT_VERSION,
            "environment": os.getenv("ENVIRONMENT", "development"),
        }
        
        # Добавляем exception если есть
        if record["exception"]:
            log_entry["exception"] = str(record["exception"])
            log_entry["traceback"] = record["exception"].traceback
        
        # Отправляем в Logstash
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # Таймаут 2 секунды
        sock.connect((LOGSTASH_HOST, LOGSTASH_PORT))
        sock.sendall((json.dumps(log_entry, ensure_ascii=False) + "\n").encode("utf-8"))
        sock.close()
    except Exception:
        pass

logger.remove()

logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> <cyan>{name}</cyan>:<cyan>{line}</cyan>[<cyan>{process}</cyan>] <level>{level: <8}</level>: <level>{message}</level>",
    level=LOG_LEVEL,
    colorize=True,
)

logger.add(
    LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} {name}:{line}[{process}] {level}: {message}",
    level=LOG_LEVEL,
    encoding="utf-8",
    rotation="10 MB",
    retention="30 days",
    compression="tar",
)

logger.add(
    ERRORS_LOG_FILE,
    format="{time:YYYY-MM-DD HH:mm:ss} {name}:{line}[{process}] {level}: {message}\n{exception}",
    level="ERROR",
    encoding="utf-8",
    rotation="10 MB",
    retention="30 days",
    compression="tar",
    backtrace=True,
    diagnose=True
)

if LOGSTASH_HOST and LOGSTASH_PORT:
    try:
        logstash_handler = logger.add(
            logstash_sink,
            level=LOG_LEVEL,  # Можно изменить на "INFO" если не хотим отправлять DEBUG в Logstash
            format="{message}",  # Формат не важен, мы формируем JSON вручную
            serialize=False,  # Не используем встроенную сериализацию
        )
        logger.info(f"Logstash logging enabled: {LOGSTASH_HOST}:{LOGSTASH_PORT}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to enable Logstash logging: {e}")
else:
    logger.info("ℹ️ Logstash logging disabled (LOGSTASH_HOST or LOGSTASH_PORT not set)")

if LOG_LEVEL == "DEBUG":
    logger.debug("=" * 50)
    logger.debug("DEBUG MODE ENABLED")
    logger.debug("=" * 50)
    logger.debug(f"Log file: {LOG_FILE}")
    logger.debug(f"Current log level: {LOG_LEVEL}")
else:
    logger.info(f"Debug messages are hidden (current level: {LOG_LEVEL})")

if __name__ == "__main__":
    try:
        logger.info("Starting application...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application stopped by user (KeyboardInterrupt)")
        sys.exit(0)
    except Exception as e:
        logger.exception(f"Unhandled exception: {e}")
        sys.exit(1)

# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from loguru import logger
from miniopy_async import Minio

from app.config.config import (
    MINIO_BUCKET_NAME,
    MINIO_HOST,
    MINIO_INTERNAL_PORT,
    MINIO_ROOT_PASSWORD,
    MINIO_ROOT_USER,
)

_client = None
_initialized = False

async def get_minio_client():
    """Get MinIO client, initializing it if necessary"""
    global _client, _initialized
    
    if not _initialized:
        await init_minio()
        await init_bucket()
        _initialized = True
    
    return _client

async def init_minio():
    logger.debug(f"Initializing Minio client with host: {MINIO_HOST}:{MINIO_INTERNAL_PORT}")

    global _client
    
    _client = Minio(
        f"{MINIO_HOST}:{MINIO_INTERNAL_PORT}",
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False,
    )

    logger.debug("Minio client created")
    return _client

async def init_bucket():
    logger.info(f"Checking if bucket '{MINIO_BUCKET_NAME}' exists...")

    try:
        exists = await _client.bucket_exists(MINIO_BUCKET_NAME)

        if exists:
            logger.info(f"Bucket '{MINIO_BUCKET_NAME}' already exists")
        else:
            logger.info(f"Bucket '{MINIO_BUCKET_NAME}' does not exist, creating...")
            await _client.make_bucket(MINIO_BUCKET_NAME)
            logger.success(f"Bucket '{MINIO_BUCKET_NAME}' created successfully")

    except Exception as e:
        logger.exception(f"Error while initializing bucket '{MINIO_BUCKET_NAME}': {e}")
        raise
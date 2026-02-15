from loguru import logger
from miniopy_async import Minio

from app.config.config import (
    MINIO_BUCKET_NAME,
    MINIO_HOST,
    MINIO_INTERNAL_PORT,
    MINIO_ROOT_PASSWORD,
    MINIO_ROOT_USER,
)

client = None

async def init_minio():
    logger.debug(f"Initializing Minio client with host: {MINIO_HOST}:{MINIO_INTERNAL_PORT}")

    global client
    
    client = Minio(
        f"{MINIO_HOST}:{MINIO_INTERNAL_PORT}",
        access_key=MINIO_ROOT_USER,
        secret_key=MINIO_ROOT_PASSWORD,
        secure=False,
    )

    logger.debug("Minio client created")

async def init_bucket():
    logger.info(f"Checking if bucket '{MINIO_BUCKET_NAME}' exists...")

    try:
        exists = await client.bucket_exists(MINIO_BUCKET_NAME)

        if exists:
            logger.info(f"Bucket '{MINIO_BUCKET_NAME}' already exists")
        else:
            logger.info(f"Bucket '{MINIO_BUCKET_NAME}' does not exist, creating...")
            await client.make_bucket(MINIO_BUCKET_NAME)
            logger.success(f"Bucket '{MINIO_BUCKET_NAME}' created successfully")

    except Exception as e:
        logger.exception(f"Error while initializing bucket '{MINIO_BUCKET_NAME}': {e}")
        raise

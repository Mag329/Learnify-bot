from miniopy_async import Minio

from app.config.config import MINIO_HOST, MINIO_INTERNAL_PORT, MINIO_ROOT_PASSWORD, MINIO_ROOT_USER, MINIO_BUCKET_NAME

client = Minio(
    f'{MINIO_HOST}:{MINIO_INTERNAL_PORT}',
    access_key=MINIO_ROOT_USER,
    secret_key=MINIO_ROOT_PASSWORD,
    secure=False
)


async def init_bucket():
    exists = await client.bucket_exists(MINIO_BUCKET_NAME)
    if not exists:
        await client.make_bucket(MINIO_BUCKET_NAME)
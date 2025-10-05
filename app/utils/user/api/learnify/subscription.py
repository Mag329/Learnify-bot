from learnifyapi.client import LearnifyAPI
from learnifyapi.exceptions import APIError

from app.config.config import LEARNIFY_API_TOKEN
from app.utils.database import AsyncSessionLocal, User, db
from app.utils.user.decorators import handle_api_error



@handle_api_error()
async def get_user_info(user_id):
    async with AsyncSessionLocal() as session:
        query = db.select(User).filter_by(user_id=user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()

        if not user:
            return None

        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                info = await api.get_user(user_id)
            except APIError as e:
                info = None
            return info
        
        
@handle_api_error()
async def create_subscription(user_id, expires_at):
    async with AsyncSessionLocal() as session:
        query = db.select(User).filter_by(user_id=user_id)
        result = await session.execute(query)
        user = result.scalar_one_or_none()
        
        if not user:
            return None, None
        
        async with LearnifyAPI(token=LEARNIFY_API_TOKEN) as api:
            try:
                result = await api.create_user(user_id=user_id, expires_at=expires_at)
            except APIError as e:
                if e.status_code == 400:
                    result = await api.update_user(user_id=user_id, expires_at=expires_at, is_active=True)
        
        return result, user
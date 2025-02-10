import logging
from octodiary.exceptions import APIError

from config import ERROR_403_MESSAGE, ERROR_408_MESSAGE, ERROR_MESSAGE, ERROR_500_MESSAGE
import app.keyboards.user.keyboards as kb


def handle_api_error():
    from app.utils.user.utils import user_send_message

    def decorator(func):
        async def wrapper(user_id, *args, **kwargs):
            try:
                return await func(user_id, *args, **kwargs)
            except APIError as e:
                if e.status_code in [401, 403]:
                    await user_send_message(user_id, ERROR_403_MESSAGE, kb.reauth)
                elif e.status_code == 408:
                    await user_send_message(user_id, ERROR_408_MESSAGE, kb.delete_message)
                elif e.status_code in [500, 501, 502]:
                    await user_send_message(user_id, ERROR_500_MESSAGE, kb.delete_message)
                else:
                    await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)
            except Exception as e:
                await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)

        return wrapper

    return decorator

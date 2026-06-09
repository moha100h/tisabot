from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Awaitable, Any
from db.database import AsyncSessionLocal
from db.repository import get_user
import logging

logger = logging.getLogger("middleware")

class AuthMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable[[TelegramObject, dict], Awaitable[Any]],
                       event: TelegramObject, data: dict) -> Any:
        if isinstance(event, (Message, CallbackQuery)):
            tg_user = event.from_user
            if tg_user:
                async with AsyncSessionLocal() as db:
                    user = await get_user(db, tg_user.id)
                data["db_user"] = user
                data["is_registered"] = user is not None
                if user and user.is_blocked:
                    if isinstance(event, Message):
                        await event.answer("⛔️ حساب شما مسدود شده است.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⛔️ حساب شما مسدود شده است.", show_alert=True)
                    return
        return await handler(event, data)

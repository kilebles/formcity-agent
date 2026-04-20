from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from loguru import logger

from app.config import settings


class AllowlistMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not settings.allowed_usernames:
            return await handler(event, data)

        if not isinstance(event, Message):
            return await handler(event, data)

        username = event.from_user.username if event.from_user else None
        if username and username.lower() in [u.lower() for u in settings.allowed_usernames]:
            return await handler(event, data)

        logger.warning(
            "Blocked user {user_id} (@{username}) — not in allowlist",
            user_id=event.from_user.id if event.from_user else "unknown",
            username=username,
        )
        await event.answer(
            "У вас нет доступа к этому боту.\n"
            "Обратитесь к администратору, если считаете, что это ошибка."
        )
        return None

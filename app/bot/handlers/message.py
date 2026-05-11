from __future__ import annotations

import asyncio

from aiogram import Router
from aiogram.enums import ChatAction
from aiogram.types import Message
from loguru import logger

from app.services.ai import ask
from app.services.history import append_history, get_history

router = Router(name="message")


async def _keep_typing(message: Message, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        await message.bot.send_chat_action(
            chat_id=message.chat.id,
            action=ChatAction.TYPING,
        )
        await asyncio.sleep(4)


@router.message()
async def handle_message(message: Message) -> None:
    user_id = message.from_user.id
    username = message.from_user.username
    text = message.text or ""

    logger.info(
        "Message from {user_id} (@{username}): {preview}",
        user_id=user_id,
        username=username,
        preview=text[:80],
    )

    history = await get_history(user_id)

    stop_event = asyncio.Event()
    typing_task = asyncio.create_task(_keep_typing(message, stop_event))

    try:
        reply = await ask(text, history)
    finally:
        stop_event.set()
        typing_task.cancel()

    await append_history(user_id, text, reply)
    await message.answer(reply)
    logger.debug("Replied to {user_id}, len={n}", user_id=user_id, n=len(reply))

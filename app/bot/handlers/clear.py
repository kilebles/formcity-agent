from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from app.services.history import clear_history

router = Router(name="clear")


@router.message(Command("clear"))
async def cmd_clear(message: Message) -> None:
    user_id = message.from_user.id
    await clear_history(user_id)
    logger.info("History cleared for user {user_id}", user_id=user_id)
    await message.answer("Контекст диалога очищен.")

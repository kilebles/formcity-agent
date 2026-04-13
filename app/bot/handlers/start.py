from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from loguru import logger

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    logger.info(
        "User {user_id} (@{username}) triggered /start",
        user_id=message.from_user.id,
        username=message.from_user.username,
    )
    await message.answer(
        "Добро пожаловать в <b>Formula City Bot</b>!\n\n"
        "Я — внутренний ИИ-помощник для сотрудников Formula City.\n\n"
        "Напишите мне любой вопрос:\n"
        "• Найду информацию о недвижимости из базы данных\n"
        "• Получу данные о проектах Well и Евгеньевский\n"
        "• Отвечу на вопросы о компании\n"
        "• Проанализирую данные из таблиц\n"
        "• Запущу поиск в интернете при необходимости\n\n"
        "Просто напишите свой вопрос текстом!"
    )
    logger.debug("Sent welcome message to user {user_id}", user_id=message.from_user.id)

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from loguru import logger

from app.bot.commands import BOT_COMMANDS
from app.bot.router import main_router
from app.config import settings


async def on_startup(bot: Bot) -> None:
    await bot.set_my_commands(BOT_COMMANDS)
    me = await bot.get_me()
    logger.info("Bot started: @{username} (id={id})", username=me.username, id=me.id)


async def on_shutdown(bot: Bot) -> None:
    logger.info("Bot stopped")


async def main() -> None:
    from app.logger import setup_logging
    setup_logging()

    logger.info("Initializing bot...")

    session = None
    if settings.proxy:
        proxy = settings.proxy
        if "://" in proxy:
            proxy_url = proxy
        else:
            parts = proxy.split(":")
            if len(parts) == 4:
                host, port, user, password = parts
                proxy_url = f"http://{user}:{password}@{host}:{port}"
            else:
                proxy_url = f"http://{proxy}"
        session = AiohttpSession(proxy=proxy_url)

    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=None),
        session=session,
    )

    dp = Dispatcher()
    dp.include_router(main_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info("Starting polling...")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
    )

from aiogram import Router

from app.bot.handlers.clear import router as clear_router
from app.bot.handlers.message import router as message_router
from app.bot.handlers.start import router as start_router
from app.bot.middleware import AllowlistMiddleware

main_router = Router(name="main")
main_router.message.middleware(AllowlistMiddleware())
main_router.include_routers(
    start_router,
    clear_router,
    message_router,
)

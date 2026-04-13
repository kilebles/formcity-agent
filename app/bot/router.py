from aiogram import Router

from app.bot.handlers.message import router as message_router
from app.bot.handlers.start import router as start_router

main_router = Router(name="main")
main_router.include_routers(
    start_router,
    message_router,
)

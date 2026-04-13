import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from bot.config import settings
from bot.db.connection import init_db
from bot.handlers import answer, callbacks, domains, help, question, settings as settings_handler, start, stats, streak
from bot.services.manifold import ManifoldClient
from bot.services.scheduler import add_schedules, create_scheduler

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

bot = Bot(token=settings.telegram_bot_token)
manifold_client = ManifoldClient()


async def main() -> None:
    await init_db()

    dp = Dispatcher()
    dp.include_router(start.router)
    dp.include_router(question.router)
    dp.include_router(answer.router)
    dp.include_router(stats.router)
    dp.include_router(domains.router)
    dp.include_router(streak.router)
    dp.include_router(settings_handler.router)
    dp.include_router(help.router)
    dp.include_router(callbacks.router)

    await bot.set_my_commands([
        BotCommand(command="question", description="Получить вопрос"),
        BotCommand(command="stats", description="Статистика и Brier Score"),
        BotCommand(command="domains", description="Точность по категориям"),
        BotCommand(command="streak", description="Серия ответов"),
        BotCommand(command="settings", description="Настройки"),
        BotCommand(command="help", description="Справка"),
    ])

    scheduler = create_scheduler()

    async with scheduler:
        await add_schedules(scheduler)
        await scheduler.start_in_background()
        logger.info("Scheduler started")

        try:
            logger.info("Starting bot polling...")
            await dp.start_polling(bot)
        finally:
            await manifold_client.close()
            logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())

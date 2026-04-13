from aiogram import Router, types
from aiogram.filters import Command

router = Router()

HELP_TEXT = (
    "📖 <b>Команды</b>\n\n"
    "/start — Начать работу, выбрать категории\n"
    "/question — Получить дополнительный вопрос\n"
    "/stats — Твоя статистика (Brier Score, тренды)\n"
    "/domains — Разбивка точности по категориям\n"
    "/streak — Текущая серия и лучшая серия\n"
    "/settings — Время вопроса, категории\n"
    "/help — Эта справка\n\n"
    "Чтобы ответить на вопрос, просто отправь число от 0 до 100."
)


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    await message.answer(HELP_TEXT, parse_mode="HTML")

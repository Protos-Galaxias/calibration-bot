from aiogram import Router, types
from aiogram.filters import Command

from bot.db.queries.users import get_user

router = Router()


@router.message(Command("streak"))
async def cmd_streak(message: types.Message) -> None:
    if not message.from_user:
        return

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запустите бота командой /start")

        return

    text = (
        f"🔥 <b>Серия</b>\n\n"
        f"Текущая серия: <b>{user['streak_current']}</b> дн.\n"
        f"Лучшая серия: <b>{user['streak_best']}</b> дн."
    )
    await message.answer(text, parse_mode="HTML")

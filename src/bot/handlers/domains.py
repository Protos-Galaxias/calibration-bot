from aiogram import Router, types
from aiogram.filters import Command

from bot.db.queries.users import get_user
from bot.helpers.formatting import format_domains
from bot.services.scoring import get_domain_breakdown

router = Router()


@router.message(Command("domains"))
async def cmd_domains(message: types.Message) -> None:
    if not message.from_user:
        return

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запустите бота командой /start")

        return

    domains = await get_domain_breakdown(user["id"])
    text = format_domains(domains)
    await message.answer(text, parse_mode="HTML")

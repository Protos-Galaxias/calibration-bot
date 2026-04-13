from aiogram import Router, types
from aiogram.filters import Command

from bot.db.queries.resolutions import count_user_resolutions
from bot.db.queries.users import get_user
from bot.helpers.formatting import format_stats
from bot.services.scoring import get_market_brier, get_overall_brier, get_rolling_brier

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: types.Message) -> None:
    if not message.from_user:
        return

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запустите бота командой /start")

        return

    overall = await get_overall_brier(user["id"])
    rolling = await get_rolling_brier(user["id"])
    market = await get_market_brier(user["id"])
    resolutions = await count_user_resolutions(user["id"])

    text = format_stats(
        total_answers=user["total_answers"],
        total_resolutions=resolutions,
        overall_brier=overall,
        rolling_brier=rolling,
        market_brier=market,
        streak_current=user["streak_current"],
        streak_best=user["streak_best"],
    )
    await message.answer(text, parse_mode="HTML")

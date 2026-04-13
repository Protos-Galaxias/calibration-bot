import logging
from datetime import date

from aiogram import Router, types

from bot.db.queries.answers import create_answer
from bot.db.queries.pending import clear_pending_question, get_pending_question_id
from bot.db.queries.questions import get_question_by_id
from bot.db.queries.users import get_user, increment_answers, update_phase, update_streak
from bot.helpers.formatting import CALIBRATION_GOAL, format_answer_response, format_calibration_complete
from bot.services.scoring import get_domain_breakdown, get_overall_brier

logger = logging.getLogger(__name__)
router = Router()


@router.message(lambda m: m.text and m.text.strip().replace("%", "").replace(",", ".").replace(" ", "").lstrip("-").isdigit())
async def on_answer(message: types.Message) -> None:
    if not message.from_user or not message.text:
        return

    tg_id = message.from_user.id
    question_id = await get_pending_question_id(tg_id)
    if not question_id:
        return

    raw = message.text.strip().replace("%", "").replace(",", ".").replace(" ", "")
    try:
        value = float(raw)
    except ValueError:
        await message.answer("Введи число от 0 до 100.")

        return

    if value < 0 or value > 100:
        await message.answer("Введи число от 0 до 100.")

        return

    user = await get_user(tg_id)
    if not user:
        return

    question = await get_question_by_id(question_id)
    if not question:
        return

    user_prob = value / 100.0

    from bot.main import manifold_client
    try:
        market_prob = await manifold_client.get_prob(question["manifold_id"])
    except Exception:
        market_prob = question["market_prob"]

    await create_answer(user["id"], question_id, user_prob, market_prob)
    await clear_pending_question(tg_id)

    await message.answer(format_answer_response(user_prob, market_prob), parse_mode="HTML")

    today = date.today().isoformat()
    await update_streak(user["id"], today)
    updated_user = await increment_answers(user["id"])

    if updated_user["total_answers"] == CALIBRATION_GOAL and updated_user["phase"] == "calibration":
        await update_phase(user["id"], "personalized")
        overall = await get_overall_brier(user["id"])
        domains = await get_domain_breakdown(user["id"])
        if overall is not None:
            text = format_calibration_complete(overall, domains)
            await message.answer(text, parse_mode="HTML")

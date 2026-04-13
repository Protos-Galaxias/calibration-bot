import logging

from bot.db.queries.answers import get_answers_for_question
from bot.db.queries.questions import get_unresolved_with_answers, mark_resolved
from bot.db.queries.resolutions import create_resolution, resolution_exists
from bot.services.manifold import ManifoldClient
from bot.services.scoring import brier_score

logger = logging.getLogger(__name__)


async def check_resolutions(manifold_client: ManifoldClient, bot) -> list[dict]:
    """Check all unresolved questions for resolutions. Returns list of notifications to send."""
    questions = await get_unresolved_with_answers()
    notifications: list[dict] = []

    for q in questions:
        try:
            market = await manifold_client.get_market(q["manifold_id"])
        except Exception:
            logger.exception("Failed to fetch market %s", q["manifold_id"])
            continue

        if not market.get("isResolved"):
            continue

        resolution = market.get("resolution")
        if resolution not in ("YES", "NO"):
            await mark_resolved(q["id"], resolution or "CANCEL", market.get("resolutionTime", ""))
            continue

        outcome = 1 if resolution == "YES" else 0
        res_time = market.get("resolutionTime", "")

        await mark_resolved(q["id"], resolution, str(res_time))

        answers = await get_answers_for_question(q["id"])
        for ans in answers:
            if await resolution_exists(ans["id"]):
                continue

            user_b = brier_score(ans["user_prob"], outcome)
            market_b = brier_score(ans["market_prob_at_answer"], outcome)

            await create_resolution(ans["id"], outcome, user_b, market_b)

            notifications.append({
                "user_id": ans["user_id"],
                "question_text": q["question_text"],
                "resolution": resolution,
                "user_prob": ans["user_prob"],
                "market_prob": ans["market_prob_at_answer"],
                "user_brier": user_b,
                "market_brier": market_b,
            })

    return notifications

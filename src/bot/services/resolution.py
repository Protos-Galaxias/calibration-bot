import logging

from bot.db.queries.answers import get_answers_for_question
from bot.db.queries.questions import get_unresolved_with_answers, mark_resolved
from bot.db.queries.resolutions import create_resolution, resolution_exists
from bot.services.scoring import brier_score
from bot.services.sources import SourcesRegistry

logger = logging.getLogger(__name__)


async def check_resolutions(registry: SourcesRegistry, bot) -> list[dict]:
    """Check all unresolved questions for resolutions. Returns list of notifications to send."""
    questions = await get_unresolved_with_answers()
    notifications: list[dict] = []

    for q in questions:
        source_name = q["source"] if "source" in q.keys() and q["source"] else "manifold"
        source = registry.get(source_name)
        if not source:
            logger.warning("No registered source %r for question %s", source_name, q["id"])
            continue

        try:
            resolution = await source.get_resolution(q["source_id"])
        except Exception:
            logger.exception("Failed to fetch resolution for %s/%s", source_name, q["source_id"])
            continue

        if not resolution:
            continue

        res_time = resolution.resolved_at.isoformat() if resolution.resolved_at else ""

        if resolution.outcome not in ("YES", "NO"):
            await mark_resolved(q["id"], resolution.outcome or "CANCEL", res_time)
            continue

        outcome = 1 if resolution.outcome == "YES" else 0

        await mark_resolved(q["id"], resolution.outcome, res_time)

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
                "resolution": resolution.outcome,
                "user_prob": ans["user_prob"],
                "market_prob": ans["market_prob_at_answer"],
                "user_brier": user_b,
                "market_brier": market_b,
            })

    return notifications

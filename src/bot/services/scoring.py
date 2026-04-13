from datetime import datetime, timedelta, timezone

from bot.db.queries.resolutions import get_user_resolutions, get_user_resolutions_by_category, get_user_resolutions_since


def brier_score(prob: float, outcome: int) -> float:
    return (prob - outcome) ** 2


async def get_overall_brier(user_id: int) -> float | None:
    rows = await get_user_resolutions(user_id)
    if not rows:
        return None

    return sum(r["user_brier"] for r in rows) / len(rows)


async def get_rolling_brier(user_id: int, days: int = 30) -> float | None:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await get_user_resolutions_since(user_id, since)
    if not rows:
        return None

    return sum(r["user_brier"] for r in rows) / len(rows)


async def get_market_brier(user_id: int) -> float | None:
    rows = await get_user_resolutions(user_id)
    if not rows:
        return None

    return sum(r["market_brier"] for r in rows) / len(rows)


async def get_rolling_market_brier(user_id: int, days: int = 30) -> float | None:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await get_user_resolutions_since(user_id, since)
    if not rows:
        return None

    return sum(r["market_brier"] for r in rows) / len(rows)


async def get_domain_breakdown(user_id: int) -> list[dict]:
    rows = await get_user_resolutions_by_category(user_id)

    return [
        {
            "category": r["category"],
            "count": r["cnt"],
            "user_brier": r["avg_user_brier"],
            "market_brier": r["avg_market_brier"],
            "expert_edge": r["avg_user_brier"] - r["avg_market_brier"],
        }
        for r in rows
    ]

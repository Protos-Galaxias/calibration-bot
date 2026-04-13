import json
import logging
from datetime import datetime, timezone

from aiosqlite import Row

from bot.db.queries.questions import count_cached_by_category, get_unused_question_for_user, question_exists, upsert_question
from bot.services.categorizer import categorize, is_meta_question
from bot.services.manifold import ManifoldClient

logger = logging.getLogger(__name__)

MIN_VOLUME = 100
MIN_PROB = 0.10
MAX_PROB = 0.90
MIN_HORIZON_DAYS = 3
MAX_HORIZON_DAYS = 180
CACHE_THRESHOLD = 5

CATEGORY_TOPIC_SLUGS: dict[str, list[str]] = {
    "politics": ["politics", "us-politics", "elections", "geopolitics"],
    "technology": ["technology", "ai", "science", "crypto"],
    "sports": ["sports", "nfl", "nba", "soccer"],
    "culture": ["entertainment", "movies", "music", "gaming"],
    "business": ["business", "economics", "finance", "markets"],
    "misc": [],
}


async def _fetch_and_cache(client: ManifoldClient, target_category: str) -> int:
    """Fetch markets from Manifold, filter, categorize, and store. Return count of new questions cached."""
    now = datetime.now(timezone.utc)
    cached = 0

    topic_slugs = CATEGORY_TOPIC_SLUGS.get(target_category, [])
    searches: list[str | None] = [None]
    for slug in topic_slugs[:3]:
        searches.append(slug)

    for topic_slug in searches:
        markets = await client.search_markets(sort="liquidity", limit=100, topic_slug=topic_slug)

        for m in markets:
            if m.is_resolved:
                continue
            if m.volume < MIN_VOLUME:
                continue
            if m.probability < MIN_PROB or m.probability > MAX_PROB:
                continue
            if is_meta_question(m.question, m.group_slugs):
                continue

            if not m.close_time:
                continue

            try:
                close_dt = datetime.fromtimestamp(m.close_time / 1000, tz=timezone.utc)
            except (ValueError, OSError, OverflowError):
                continue

            horizon = (close_dt - now).days
            if horizon < MIN_HORIZON_DAYS or horizon > MAX_HORIZON_DAYS:
                continue

            if await question_exists(m.id):
                continue

            category = await categorize(m.question, m.group_slugs)

            await upsert_question(
                manifold_id=m.id,
                question_text=m.question,
                category=category,
                market_prob=m.probability,
                close_time=close_dt.isoformat(),
                volume=m.volume,
                url=m.url,
            )
            cached += 1

        if cached >= CACHE_THRESHOLD:
            break

    logger.info("Cached %d new questions from Manifold (target: %s)", cached, target_category)

    return cached


def _pick_category(user_categories: list[str], answer_counts: dict[str, int]) -> str:
    """Round-robin: pick the category with the fewest answers."""
    min_count = float("inf")
    best = user_categories[0]
    for cat in user_categories:
        cnt = answer_counts.get(cat, 0)
        if cnt < min_count:
            min_count = cnt
            best = cat

    return best


async def pick_question(
    user_row: Row,
    manifold_client: ManifoldClient,
) -> Row | None:
    """Pick a question for the user. Returns a question Row or None if nothing available."""
    categories: list[str] = json.loads(user_row["categories"])
    user_id: int = user_row["id"]

    from bot.db.connection import get_db

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT q.category, COUNT(*) as cnt
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ?
            GROUP BY q.category
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()

    answer_counts = {r["category"]: r["cnt"] for r in rows}
    target_cat = _pick_category(categories, answer_counts)

    question = await get_unused_question_for_user(user_id, target_cat)
    if question:
        return question

    cache_count = await count_cached_by_category(target_cat)
    if cache_count < CACHE_THRESHOLD:
        await _fetch_and_cache(manifold_client, target_cat)
        question = await get_unused_question_for_user(user_id, target_cat)
        if question:
            return question

    for cat in categories:
        if cat == target_cat:
            continue
        question = await get_unused_question_for_user(user_id, cat)
        if question:
            return question

        cache_count = await count_cached_by_category(cat)
        if cache_count < CACHE_THRESHOLD:
            await _fetch_and_cache(manifold_client, cat)
            question = await get_unused_question_for_user(user_id, cat)
            if question:
                return question

    return None

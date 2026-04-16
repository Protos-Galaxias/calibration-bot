import json
import logging
from datetime import datetime, timezone

from aiosqlite import Row

from bot.db.queries.questions import count_cached_by_subcategory, get_unused_question_for_user, question_exists, upsert_question
from bot.db.queries.users import get_blocked_tags
from bot.models.user import parent_category
from bot.services.categorizer import categorize, is_meta_question, is_personal_question
from bot.services.manifold import ManifoldClient

logger = logging.getLogger(__name__)

MIN_VOLUME = 100
MIN_PROB = 0.10
MAX_PROB = 0.90
STALE_PROB_LOW = 0.05
STALE_PROB_HIGH = 0.95
MIN_HORIZON_DAYS = 1
MAX_HORIZON_DAYS = 14
CACHE_THRESHOLD = 5

SUBCATEGORY_TOPIC_SLUGS: dict[str, list[str]] = {
    # Politics
    "us-politics": ["us-politics", "trump", "congress"],
    "eu-politics": ["eu-politics", "uk-politics"],
    "russia-ukraine": ["russia", "ukraine"],
    "china-asia": ["china", "india", "asia"],
    "elections": ["elections", "2024-us-presidential-election"],
    "geopolitics": ["geopolitics", "international-relations", "nato"],
    # Technology
    "ai-ml": ["ai", "artificial-intelligence", "machine-learning"],
    "crypto": ["crypto", "bitcoin", "ethereum"],
    "space": ["space", "spacex", "nasa"],
    "biotech": ["biotech", "science", "medicine"],
    "software": ["technology", "programming", "software"],
    # Sports
    "football-soccer": ["soccer", "premier-league", "champions-league"],
    "basketball": ["nba", "basketball"],
    "nfl": ["nfl", "american-football"],
    "other-sports": ["sports", "baseball", "tennis", "f1"],
    # Culture
    "movies-tv": ["movies", "tv", "entertainment"],
    "music": ["music", "spotify"],
    "gaming": ["gaming", "video-games"],
    # Business
    "stock-markets": ["stock-market", "markets", "finance"],
    "macro": ["economics", "inflation", "fed"],
    "companies": ["business", "startups", "venture-capital"],
    # Misc
    "misc": [],
}


def _has_blocked_tag(group_slugs: list[str], blocked_tags: set[str]) -> bool:
    if not blocked_tags:
        return False
    slugs = {s.lower() for s in group_slugs}

    return bool(slugs & blocked_tags)


async def _fetch_and_cache(client: ManifoldClient, target_subcategory: str, blocked_tags: set[str] | None = None) -> int:
    """Fetch markets from Manifold, filter, categorize, and store. Return count of new questions cached."""
    now = datetime.now(timezone.utc)
    cached = 0

    topic_slugs = SUBCATEGORY_TOPIC_SLUGS.get(target_subcategory, [])
    searches: list[str | None] = [None]
    for slug in topic_slugs[:3]:
        searches.append(slug)

    for topic_slug in searches:
        try:
            markets = await client.search_markets(sort="close-date", limit=100, topic_slug=topic_slug)
        except Exception:
            logger.warning("Failed to fetch markets for topic_slug=%s, skipping", topic_slug)
            continue

        for m in markets:
            if m.is_resolved:
                continue
            if m.volume < MIN_VOLUME:
                continue
            if m.probability < MIN_PROB or m.probability > MAX_PROB:
                continue
            if is_meta_question(m.question, m.group_slugs):
                continue
            if is_personal_question(m.question, m.group_slugs):
                continue
            if _has_blocked_tag(m.group_slugs, blocked_tags or set()):
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

            category, subcategory = await categorize(m.question, m.group_slugs)

            await upsert_question(
                manifold_id=m.id,
                question_text=m.question,
                category=category,
                subcategory=subcategory,
                market_prob=m.probability,
                close_time=close_dt.isoformat(),
                volume=m.volume,
                url=m.url,
                tags=json.dumps(m.group_slugs),
            )
            cached += 1

        if cached >= CACHE_THRESHOLD:
            break

    logger.info("Cached %d new questions from Manifold (target subcat: %s)", cached, target_subcategory)

    return cached


def _pick_subcategory(user_subcategories: list[str], answer_counts: dict[str, int]) -> str:
    """Round-robin: pick the subcategory with the fewest answers."""
    min_count = float("inf")
    best = user_subcategories[0]
    for subcat in user_subcategories:
        cnt = answer_counts.get(subcat, 0)
        if cnt < min_count:
            min_count = cnt
            best = subcat

    return best


def _matches_blocked_tags(question_row: Row, blocked: set[str]) -> bool:
    if not blocked:
        return False
    raw = question_row["tags"] if "tags" in question_row.keys() else "[]"
    tags = {t.lower() for t in json.loads(raw or "[]")}

    return bool(tags & blocked)


async def _get_unblocked_question(user_id: int, subcategory: str, blocked: set[str]) -> Row | None:
    for _ in range(20):
        q = await get_unused_question_for_user(user_id, subcategory)
        if not q:
            return None
        if not _matches_blocked_tags(q, blocked):
            return q

    return None


def _effective_subcategory(question_row: Row) -> str:
    """Get subcategory from question row, falling back to parent category."""
    subcat = question_row["subcategory"] if "subcategory" in question_row.keys() else None
    if subcat:
        return subcat

    return question_row["category"]


_MAX_FRESHNESS_ATTEMPTS = 5


async def _is_still_interesting(question_row: Row, client: ManifoldClient) -> bool:
    """Check live probability — skip markets where the outcome is already obvious."""
    try:
        prob = await client.get_prob(question_row["manifold_id"])
    except Exception:
        return True

    return STALE_PROB_LOW <= prob <= STALE_PROB_HIGH


async def _pick_fresh_question(
    user_id: int,
    subcategory: str,
    blocked: set[str],
    client: ManifoldClient,
) -> Row | None:
    """Get an unblocked question and verify its live prob is still interesting."""
    for _ in range(_MAX_FRESHNESS_ATTEMPTS):
        q = await _get_unblocked_question(user_id, subcategory, blocked)
        if not q:
            return None
        if await _is_still_interesting(q, client):
            return q
        logger.info("Skipping stale market %s (prob moved to extreme)", q["manifold_id"])

    return None


async def pick_question(
    user_row: Row,
    manifold_client: ManifoldClient,
) -> Row | None:
    """Pick a question for the user. Returns a question Row or None if nothing available."""
    subcategories: list[str] = json.loads(user_row["categories"])
    user_id: int = user_row["id"]
    tg_id: int = user_row["telegram_id"]

    blocked = set(await get_blocked_tags(tg_id))

    from bot.db.connection import get_db

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT COALESCE(q.subcategory, q.category) as effective_subcat, COUNT(*) as cnt
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ?
            GROUP BY effective_subcat
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()

    answer_counts = {r["effective_subcat"]: r["cnt"] for r in rows}
    target_subcat = _pick_subcategory(subcategories, answer_counts)

    question = await _pick_fresh_question(user_id, target_subcat, blocked, manifold_client)
    if question:
        return question

    cache_count = await count_cached_by_subcategory(target_subcat)
    if cache_count < CACHE_THRESHOLD:
        await _fetch_and_cache(manifold_client, target_subcat, blocked)
        question = await _pick_fresh_question(user_id, target_subcat, blocked, manifold_client)
        if question:
            return question

    for subcat in subcategories:
        if subcat == target_subcat:
            continue
        question = await _pick_fresh_question(user_id, subcat, blocked, manifold_client)
        if question:
            return question

        cache_count = await count_cached_by_subcategory(subcat)
        if cache_count < CACHE_THRESHOLD:
            await _fetch_and_cache(manifold_client, subcat, blocked)
            question = await _pick_fresh_question(user_id, subcat, blocked, manifold_client)
            if question:
                return question

    return None

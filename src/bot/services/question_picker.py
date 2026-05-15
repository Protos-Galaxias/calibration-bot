import json
import logging
from datetime import datetime, timezone

from aiosqlite import Row

from bot.db.queries.questions import (
    count_usable_cached_by_subcategory_for_user,
    get_unused_questions_for_user,
    question_exists,
    update_tags,
    upsert_question,
)
from bot.db.queries.users import get_blocked_tags
from bot.services.categorizer import categorize, is_meta_question, is_personal_question
from bot.services.sources import MarketSource, NormalizedMarket, SourcesRegistry

logger = logging.getLogger(__name__)

MIN_PROB = 0.10
MAX_PROB = 0.90
STALE_PROB_LOW = 0.05
STALE_PROB_HIGH = 0.95
MIN_HORIZON_DAYS = 1
MAX_HORIZON_DAYS = 14
CACHE_THRESHOLD = 5
CANDIDATE_LIMIT = 50
PER_SOURCE_FETCH_LIMIT = 30
_MAX_FRESHNESS_ATTEMPTS = 20


def _normalize_tag(tag: str) -> str:
    return tag.lower()


def _tags_match_blocked(tags: list[str], blocked: set[str]) -> bool:
    if not blocked:
        return False
    norm_tags = {_normalize_tag(t) for t in tags}
    norm_blocked = {_normalize_tag(t) for t in blocked}

    return bool(norm_tags & norm_blocked)


def _row_tags(question_row: Row) -> list[str]:
    raw = question_row["tags"] if "tags" in question_row.keys() else "[]"

    return json.loads(raw or "[]")


def _row_source(question_row: Row) -> str:
    if "source" in question_row.keys() and question_row["source"]:
        return question_row["source"]

    return "manifold"


def _passes_static_filters(market: NormalizedMarket, *, source: MarketSource, now: datetime) -> bool:
    if market.is_resolved:
        return False
    if market.probability < MIN_PROB or market.probability > MAX_PROB:
        return False
    if market.volume < source.min_volume:
        return False
    horizon = (market.close_time - now).days
    if horizon < MIN_HORIZON_DAYS or horizon > MAX_HORIZON_DAYS:
        return False

    return True


async def _cache_one(market: NormalizedMarket) -> None:
    category, subcategory = await categorize(market.question, market.tags)

    await upsert_question(
        source=market.source,
        source_id=market.source_id,
        question_text=market.question,
        category=category,
        subcategory=subcategory,
        market_prob=market.probability,
        close_time=market.close_time.isoformat(),
        volume=market.volume,
        url=market.url,
        tags=json.dumps(market.tags),
    )


async def _fetch_and_cache_from_source(
    source: MarketSource,
    target_subcategory: str,
    blocked_tags: set[str],
) -> int:
    try:
        candidates = await source.fetch_candidates(
            subcategory=target_subcategory, limit=PER_SOURCE_FETCH_LIMIT,
        )
    except Exception:
        logger.exception("Source %s fetch_candidates failed for subcat=%s", source.name, target_subcategory)

        return 0

    now = datetime.now(timezone.utc)
    cached = 0
    for market in candidates:
        if not _passes_static_filters(market, source=source, now=now):
            continue
        if is_meta_question(market.question, market.tags):
            continue
        if is_personal_question(market.question, market.tags):
            continue
        if _tags_match_blocked(market.tags, blocked_tags):
            continue
        if await question_exists(market.source, market.source_id):
            continue

        await _cache_one(market)
        cached += 1
        if cached >= CACHE_THRESHOLD:
            break

    if cached:
        logger.info("Cached %d new questions from %s (subcat=%s)", cached, source.name, target_subcategory)

    return cached


async def _fetch_and_cache(registry: SourcesRegistry, target_subcategory: str, blocked_tags: set[str]) -> int:
    total = 0
    for source in registry.all():
        total += await _fetch_and_cache_from_source(source, target_subcategory, blocked_tags)

    return total


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


async def _ensure_tags(question_row: Row, registry: SourcesRegistry) -> list[str]:
    """Backfill tags for rows that were cached before tag-fetching worked."""
    tags = _row_tags(question_row)
    if tags:
        return tags

    source = registry.get(_row_source(question_row))
    if not source:
        return []

    market = await source.get_market(question_row["source_id"])
    if not market or not market.tags:
        return []

    await update_tags(question_row["id"], json.dumps(market.tags))

    return market.tags


async def _get_unblocked_questions(user_id: int, subcategory: str, blocked: set[str]) -> list[Row]:
    questions = await get_unused_questions_for_user(user_id, subcategory, limit=CANDIDATE_LIMIT)
    if not blocked:
        return questions

    return [q for q in questions if not _tags_match_blocked(_row_tags(q), blocked)]


async def _is_still_interesting(question_row: Row, registry: SourcesRegistry) -> bool:
    """Check live probability — skip markets where the outcome is already obvious."""
    source = registry.get(_row_source(question_row))
    if not source:
        return True

    prob = await source.get_probability(question_row["source_id"])
    if prob is None:
        return True

    return STALE_PROB_LOW <= prob <= STALE_PROB_HIGH


async def _pick_fresh_question(
    user_id: int,
    subcategory: str,
    blocked: set[str],
    registry: SourcesRegistry,
) -> Row | None:
    questions = await _get_unblocked_questions(user_id, subcategory, blocked)
    for q in questions[:_MAX_FRESHNESS_ATTEMPTS]:
        tags = await _ensure_tags(q, registry)
        if _tags_match_blocked(tags, blocked):
            logger.info("Skipping question %s — matched blocked tag after enrichment", q["source_id"])
            continue
        if await _is_still_interesting(q, registry):
            return q
        logger.info("Skipping stale market %s/%s (prob moved to extreme)", _row_source(q), q["source_id"])

    return None


async def _pick_or_refill(
    user_id: int,
    subcategory: str,
    blocked: set[str],
    registry: SourcesRegistry,
) -> Row | None:
    cached_count = await count_usable_cached_by_subcategory_for_user(user_id, subcategory)
    fetched = False

    if cached_count < CACHE_THRESHOLD:
        await _fetch_and_cache(registry, subcategory, blocked)
        fetched = True

    question = await _pick_fresh_question(user_id, subcategory, blocked, registry)
    if question:
        return question

    if not fetched:
        await _fetch_and_cache(registry, subcategory, blocked)
        question = await _pick_fresh_question(user_id, subcategory, blocked, registry)
        if question:
            return question

    return None


async def pick_question(user_row: Row, registry: SourcesRegistry) -> Row | None:
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

    question = await _pick_or_refill(user_id, target_subcat, blocked, registry)
    if question:
        return question

    for subcat in subcategories:
        if subcat == target_subcat:
            continue

        question = await _pick_or_refill(user_id, subcat, blocked, registry)
        if question:
            return question

    return None

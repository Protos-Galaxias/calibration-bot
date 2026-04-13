import logging
import re

import httpx

from bot.config import settings

logger = logging.getLogger(__name__)

SLUG_MAP: dict[str, str] = {}

_RULES: list[tuple[str, list[str]]] = [
    ("politics", [
        "politics", "us-politics", "elections", "geopolitics", "international-relations",
        "democracy", "republicans", "democrats", "trump", "biden", "congress", "senate",
        "eu-politics", "china", "russia", "ukraine", "war", "nato", "legislation",
    ]),
    ("technology", [
        "technology", "ai", "artificial-intelligence", "machine-learning", "crypto",
        "cryptocurrency", "bitcoin", "ethereum", "science", "programming", "software",
        "openai", "google", "apple", "microsoft", "meta", "space", "spacex", "nasa",
        "robotics", "quantum-computing", "biotech",
    ]),
    ("sports", [
        "sports", "nfl", "nba", "soccer", "football", "baseball", "mlb", "tennis",
        "f1", "formula-1", "esports", "olympics", "cricket", "golf", "boxing", "mma",
        "ufc", "premier-league", "champions-league", "world-cup",
    ]),
    ("culture", [
        "entertainment", "movies", "music", "tv", "television", "celebrities",
        "oscars", "grammys", "emmys", "streaming", "netflix", "spotify", "gaming",
        "books", "art", "culture", "pop-culture", "anime", "manga",
    ]),
    ("business", [
        "business", "economics", "finance", "markets", "stock-market", "startups",
        "venture-capital", "ipo", "mergers", "acquisitions", "real-estate", "inflation",
        "fed", "interest-rates", "gdp", "unemployment", "trade", "tiktok",
    ]),
]

for category, slugs in _RULES:
    for slug in slugs:
        SLUG_MAP[slug] = category

_META_SLUGS = {"manifold", "manifold-markets", "manifold-love", "mana", "manifold-features"}
_META_PATTERNS = re.compile(
    r"\b(manifold|this market|this question|mana prize|manifold markets|trader bonus)\b",
    re.IGNORECASE,
)

_VALID_CATEGORIES = frozenset({"politics", "technology", "sports", "culture", "business", "misc"})

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def is_meta_question(question_text: str, group_slugs: list[str]) -> bool:
    if _META_SLUGS & set(group_slugs):
        return True

    return bool(_META_PATTERNS.search(question_text))


def categorize_by_slugs(group_slugs: list[str]) -> str | None:
    counts: dict[str, int] = {}
    for slug in group_slugs:
        cat = SLUG_MAP.get(slug.lower())
        if cat:
            counts[cat] = counts.get(cat, 0) + 1

    if not counts:
        return None

    return max(counts, key=counts.get)  # type: ignore[arg-type]


async def categorize_with_llm(question_text: str, group_slugs: list[str]) -> str:
    if not settings.openrouter_api_key:
        return "misc"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                },
                json={
                    "model": settings.openrouter_model,
                    "max_tokens": 20,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You classify prediction market questions into exactly one category. "
                                "Categories: politics, technology, sports, culture, business, misc. "
                                "Respond with only the category slug, nothing else."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Question: {question_text}\nTags: {', '.join(group_slugs)}",
                        },
                    ],
                },
            )
            resp.raise_for_status()
            result = resp.json()["choices"][0]["message"]["content"].strip().lower()
            if result in _VALID_CATEGORIES:
                return result
    except Exception:
        logger.exception("LLM categorization failed")

    return "misc"


async def categorize(question_text: str, group_slugs: list[str]) -> str:
    result = categorize_by_slugs(group_slugs)
    if result:
        return result

    return await categorize_with_llm(question_text, group_slugs)

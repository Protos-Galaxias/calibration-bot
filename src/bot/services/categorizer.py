import logging
import re

import httpx

from bot.config import settings
from bot.models.user import ALL_SUBCATEGORY_SLUGS, parent_category

logger = logging.getLogger(__name__)

# --- Parent category slug map (kept for backward compat) ---

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

for _category, _slugs in _RULES:
    for _slug in _slugs:
        SLUG_MAP[_slug] = _category

# --- Subcategory slug map: manifold group_slug -> our subcategory slug ---

SUBCATEGORY_SLUG_MAP: dict[str, str] = {}

_SUBCAT_RULES: list[tuple[str, list[str]]] = [
    # Politics
    ("us-politics", [
        "us-politics", "republicans", "democrats", "trump", "biden", "congress",
        "senate", "us-elections", "scotus", "supreme-court",
    ]),
    ("eu-politics", ["eu-politics", "european-union", "brexit", "uk-politics", "france", "germany"]),
    ("russia-ukraine", ["russia", "ukraine", "war", "russian-politics"]),
    ("china-asia", ["china", "india", "japan", "korea", "taiwan", "asia", "southeast-asia"]),
    ("elections", ["elections", "2024-us-presidential-election", "midterms", "voting"]),
    ("geopolitics", [
        "geopolitics", "international-relations", "nato", "united-nations",
        "middle-east", "israel", "iran", "africa", "latin-america", "politics",
        "democracy", "legislation",
    ]),
    # Technology
    ("ai-ml", [
        "ai", "artificial-intelligence", "machine-learning", "openai", "gpt",
        "deepmind", "anthropic", "llm", "chatgpt", "robotics",
    ]),
    ("crypto", ["crypto", "cryptocurrency", "bitcoin", "ethereum", "defi", "nft", "web3"]),
    ("space", ["space", "spacex", "nasa", "mars", "moon", "rockets", "astronomy"]),
    ("biotech", [
        "biotech", "biology", "medicine", "pharma", "health", "covid",
        "pandemic", "vaccine", "fda", "genetics", "science", "quantum-computing",
    ]),
    ("software", [
        "software", "programming", "technology", "google", "apple", "microsoft",
        "meta", "internet", "social-media", "startups-tech",
    ]),
    # Sports
    ("football-soccer", [
        "soccer", "football", "premier-league", "champions-league", "world-cup",
        "la-liga", "bundesliga", "serie-a",
    ]),
    ("basketball", ["nba", "basketball", "wnba"]),
    ("nfl", ["nfl", "super-bowl", "american-football"]),
    ("other-sports", [
        "sports", "baseball", "mlb", "tennis", "f1", "formula-1", "esports",
        "olympics", "cricket", "golf", "boxing", "mma", "ufc", "hockey", "nhl",
    ]),
    # Culture
    ("movies-tv", [
        "movies", "tv", "television", "oscars", "emmys", "streaming", "netflix",
        "entertainment", "celebrities", "anime", "manga",
    ]),
    ("music", ["music", "grammys", "spotify", "concerts"]),
    ("gaming", ["gaming", "video-games", "twitch", "esports-culture"]),
    # Business
    ("stock-markets", [
        "stock-market", "markets", "finance", "stocks", "sp500",
        "trading", "hedge-funds",
    ]),
    ("macro", [
        "economics", "inflation", "fed", "interest-rates", "gdp",
        "unemployment", "recession", "trade", "real-estate",
    ]),
    ("companies", [
        "business", "startups", "venture-capital", "ipo", "mergers",
        "acquisitions", "tiktok",
    ]),
]

for _subcat, _slugs in _SUBCAT_RULES:
    for _slug in _slugs:
        if _slug not in SUBCATEGORY_SLUG_MAP:
            SUBCATEGORY_SLUG_MAP[_slug] = _subcat

# --- Filters ---

_META_SLUGS = {"manifold", "manifold-markets", "manifold-love", "mana", "manifold-features"}
_META_PATTERNS = re.compile(
    r"\b(manifold|this market|this question|mana prize|manifold markets|trader bonus)\b",
    re.IGNORECASE,
)

_PERSONAL_SLUGS = {"personal", "personal-goals", "personal-life"}
_PERSONAL_PATTERNS = re.compile(
    r"(?:^|\b)(will i|am i|can i|do i|should i|have i|would i|shall i|could i|did i|"
    r"my personal|my relationship|my career|my job|my salary|my weight|"
    r"i will|i am going to|i\'ll|i\'m going to)\b",
    re.IGNORECASE,
)

_VALID_CATEGORIES = frozenset({"politics", "technology", "sports", "culture", "business", "misc"})
_VALID_SUBCATEGORIES = frozenset(ALL_SUBCATEGORY_SLUGS)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def is_meta_question(question_text: str, group_slugs: list[str]) -> bool:
    if _META_SLUGS & set(group_slugs):
        return True

    return bool(_META_PATTERNS.search(question_text))


def is_personal_question(question_text: str, group_slugs: list[str]) -> bool:
    slugs_lower = {s.lower() for s in group_slugs}
    if _PERSONAL_SLUGS & slugs_lower:
        return True

    return bool(_PERSONAL_PATTERNS.search(question_text))


# --- Categorization ---

def categorize_by_slugs(group_slugs: list[str]) -> str | None:
    counts: dict[str, int] = {}
    for slug in group_slugs:
        cat = SLUG_MAP.get(slug.lower())
        if cat:
            counts[cat] = counts.get(cat, 0) + 1

    if not counts:
        return None

    return max(counts, key=counts.get)  # type: ignore[arg-type]


def subcategorize_by_slugs(group_slugs: list[str]) -> str | None:
    counts: dict[str, int] = {}
    for slug in group_slugs:
        subcat = SUBCATEGORY_SLUG_MAP.get(slug.lower())
        if subcat:
            counts[subcat] = counts.get(subcat, 0) + 1

    if not counts:
        return None

    return max(counts, key=counts.get)  # type: ignore[arg-type]


_SUBCAT_LIST_STR = ", ".join(sorted(ALL_SUBCATEGORY_SLUGS))


async def categorize_with_llm(question_text: str, group_slugs: list[str]) -> tuple[str, str | None]:
    if not settings.openrouter_api_key:
        return "misc", None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                },
                json={
                    "model": settings.openrouter_model,
                    "max_tokens": 30,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You classify prediction market questions. "
                                "First, pick a parent category: politics, technology, sports, culture, business, misc. "
                                f"Then pick a subcategory from: {_SUBCAT_LIST_STR}. "
                                "Respond with exactly two words separated by a space: CATEGORY SUBCATEGORY. "
                                "If no subcategory fits, respond with just the category."
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
            raw = resp.json()["choices"][0]["message"]["content"].strip().lower()
            parts = raw.split()

            cat = parts[0] if parts else "misc"
            if cat not in _VALID_CATEGORIES:
                cat = "misc"

            subcat = parts[1] if len(parts) > 1 else None
            if subcat and subcat not in _VALID_SUBCATEGORIES:
                subcat = None

            return cat, subcat
    except Exception:
        logger.exception("LLM categorization failed")

    return "misc", None


async def categorize(question_text: str, group_slugs: list[str]) -> tuple[str, str | None]:
    """Return (category, subcategory) for a question."""
    subcat = subcategorize_by_slugs(group_slugs)
    if subcat:
        return parent_category(subcat), subcat

    cat = categorize_by_slugs(group_slugs)
    if cat:
        llm_cat, llm_subcat = await categorize_with_llm(question_text, group_slugs)
        if llm_subcat and parent_category(llm_subcat) == cat:
            return cat, llm_subcat

        return cat, None

    return await categorize_with_llm(question_text, group_slugs)

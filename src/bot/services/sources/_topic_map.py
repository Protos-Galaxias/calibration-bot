"""Mapping from our subcategory slugs to native topic/category slugs of each source.

Keys are our internal subcategory slugs (see bot.models.user).
Values are lists of source-native slugs to query — usually plural to broaden
the candidate pool.
"""

MANIFOLD_TOPICS: dict[str, list[str]] = {
    "us-politics": ["us-politics", "trump", "congress"],
    "eu-politics": ["eu-politics", "uk-politics"],
    "russia-ukraine": ["russia", "ukraine"],
    "china-asia": ["china", "india", "asia"],
    "elections": ["elections", "2024-us-presidential-election"],
    "geopolitics": ["geopolitics", "international-relations", "nato"],
    "ai-ml": ["ai", "artificial-intelligence", "machine-learning"],
    "crypto": ["crypto", "bitcoin", "ethereum"],
    "space": ["space", "spacex", "nasa"],
    "biotech": ["biotech", "science", "medicine"],
    "software": ["technology", "programming", "software"],
    "football-soccer": ["soccer", "premier-league", "champions-league"],
    "basketball": ["nba", "basketball"],
    "nfl": ["nfl", "american-football"],
    "other-sports": ["sports", "baseball", "tennis", "f1"],
    "movies-tv": ["movies", "tv", "entertainment"],
    "music": ["music", "spotify"],
    "gaming": ["gaming", "video-games"],
    "stock-markets": ["stock-market", "markets", "finance"],
    "macro": ["economics", "inflation", "fed"],
    "companies": ["business", "startups", "venture-capital"],
    "misc": [],
}


POLYMARKET_TAGS: dict[str, list[str]] = {
    "us-politics": ["politics", "trump", "us-elections"],
    "eu-politics": ["politics"],
    "russia-ukraine": ["ukraine", "russia"],
    "china-asia": ["china"],
    "elections": ["us-elections", "elections"],
    "geopolitics": ["geopolitics", "middle-east"],
    "ai-ml": ["ai"],
    "crypto": ["crypto", "bitcoin", "ethereum"],
    "space": ["space"],
    "biotech": ["science", "health"],
    "software": ["tech"],
    "football-soccer": ["soccer", "premier-league", "champions-league", "world-cup"],
    "basketball": ["nba"],
    "nfl": ["nfl"],
    "other-sports": ["mlb", "tennis", "f1", "ufc", "mma", "boxing"],
    "movies-tv": ["pop-culture", "entertainment"],
    "music": ["music"],
    "gaming": ["gaming"],
    "stock-markets": ["markets", "stocks"],
    "macro": ["economy"],
    "companies": ["business"],
    "misc": [],
}


METACULUS_CATEGORIES: dict[str, list[str]] = {
    "us-politics": ["politics", "elections"],
    "eu-politics": ["politics"],
    "russia-ukraine": ["geopolitics"],
    "china-asia": ["geopolitics"],
    "elections": ["elections", "politics"],
    "geopolitics": ["geopolitics"],
    "ai-ml": ["artificial-intelligence"],
    "crypto": ["economy-business"],
    "space": ["technology"],
    "biotech": ["health-pandemics"],
    "software": ["technology"],
    "football-soccer": ["sports-entertainment"],
    "basketball": ["sports-entertainment"],
    "nfl": ["sports-entertainment"],
    "other-sports": ["sports-entertainment"],
    "movies-tv": ["sports-entertainment"],
    "music": ["sports-entertainment"],
    "gaming": ["sports-entertainment"],
    "stock-markets": ["economy-business"],
    "macro": ["economy-business"],
    "companies": ["economy-business"],
    "misc": [],
}

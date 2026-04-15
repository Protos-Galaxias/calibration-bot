from typing import TypedDict


class SubcategoryGroup(TypedDict):
    label: str
    icon: str
    children: dict[str, str]


SUBCATEGORIES: dict[str, SubcategoryGroup] = {
    "politics": {
        "label": "Политика",
        "icon": "🏛",
        "children": {
            "us-politics": "US Politics",
            "eu-politics": "Европа",
            "russia-ukraine": "Россия/Украина",
            "china-asia": "Китай/Азия",
            "elections": "Выборы",
            "geopolitics": "Геополитика",
        },
    },
    "technology": {
        "label": "Технологии",
        "icon": "💻",
        "children": {
            "ai-ml": "AI/ML",
            "crypto": "Крипто",
            "space": "Космос",
            "biotech": "Биотех/Медицина",
            "software": "Софт/Интернет",
        },
    },
    "sports": {
        "label": "Спорт",
        "icon": "⚽",
        "children": {
            "football-soccer": "Футбол",
            "basketball": "Баскетбол/NBA",
            "nfl": "NFL",
            "other-sports": "Другой спорт",
        },
    },
    "culture": {
        "label": "Культура",
        "icon": "🎭",
        "children": {
            "movies-tv": "Кино/ТВ",
            "music": "Музыка",
            "gaming": "Игры",
        },
    },
    "business": {
        "label": "Бизнес",
        "icon": "💼",
        "children": {
            "stock-markets": "Рынки/Финансы",
            "macro": "Макро/Экономика",
            "companies": "Компании/Стартапы",
        },
    },
    "misc": {
        "label": "Разное",
        "icon": "🎲",
        "children": {},
    },
}

# Legacy compat: old flat dict used by formatting and other modules
CATEGORIES = {slug: f"{grp['icon']} {grp['label']}" for slug, grp in SUBCATEGORIES.items()}

ALL_CATEGORY_SLUGS: list[str] = list(CATEGORIES.keys())

# Flat map: subcategory_slug -> label
ALL_SUBCATEGORY_LABELS: dict[str, str] = {}
for _grp in SUBCATEGORIES.values():
    for _sub_slug, _sub_label in _grp["children"].items():
        ALL_SUBCATEGORY_LABELS[_sub_slug] = _sub_label

ALL_SUBCATEGORY_SLUGS: list[str] = list(ALL_SUBCATEGORY_LABELS.keys())

# Reverse map: subcategory_slug -> parent category slug
_SUBCAT_TO_PARENT: dict[str, str] = {}
for _parent_slug, _grp in SUBCATEGORIES.items():
    for _sub_slug in _grp["children"]:
        _SUBCAT_TO_PARENT[_sub_slug] = _parent_slug


def parent_category(subcategory_slug: str) -> str:
    return _SUBCAT_TO_PARENT.get(subcategory_slug, "misc")


def subcategory_label(slug: str) -> str:
    return ALL_SUBCATEGORY_LABELS.get(slug, slug)


def expand_parent_to_children(parent_slug: str) -> list[str]:
    """Expand a parent category slug into all its subcategory slugs."""
    grp = SUBCATEGORIES.get(parent_slug)
    if not grp or not grp["children"]:
        return [parent_slug]

    return list(grp["children"].keys())

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from bot.config import settings

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def _migrate_user_categories(db: aiosqlite.Connection) -> None:
    """Expand old parent-level category slugs into subcategory slugs."""
    from bot.models.user import ALL_CATEGORY_SLUGS, expand_parent_to_children

    db.row_factory = aiosqlite.Row
    cursor = await db.execute("SELECT id, categories FROM users")
    rows = await cursor.fetchall()

    for row in rows:
        cats: list[str] = json.loads(row["categories"])
        expanded: list[str] = []
        needs_update = False
        for slug in cats:
            if slug in ALL_CATEGORY_SLUGS:
                expanded.extend(expand_parent_to_children(slug))
                needs_update = True
            else:
                expanded.append(slug)

        if needs_update:
            await db.execute(
                "UPDATE users SET categories = ? WHERE id = ?",
                (json.dumps(expanded), row["id"]),
            )


async def init_db() -> None:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(path)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        schema = _SCHEMA_PATH.read_text()
        await db.executescript(schema)

        migrations: list[tuple[str, str, str]] = [
            ("questions", "tags", "'[]'"),
            ("questions", "question_text_ru", "NULL"),
            ("questions", "subcategory", "NULL"),
            ("users", "blocked_tags", "'[]'"),
        ]
        for table, col, default in migrations:
            try:
                await db.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT {default}")
            except Exception:
                pass

        await _migrate_user_categories(db)
        await db.commit()

    logger.info("Database initialized at %s", path)


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    async with aiosqlite.connect(settings.database_path) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            await db.commit()

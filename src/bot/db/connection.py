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


async def _migrate_to_multi_source(db: aiosqlite.Connection) -> None:
    """Rebuild questions table to use (source, source_id) instead of manifold_id."""
    cur = await db.execute("PRAGMA user_version")
    row = await cur.fetchone()
    version = row[0] if row else 0
    if version >= 1:
        return

    cur = await db.execute("PRAGMA table_info(questions)")
    cols = {r[1] for r in await cur.fetchall()}
    if "manifold_id" not in cols:
        await db.execute("PRAGMA user_version = 1")

        return

    await db.execute("PRAGMA foreign_keys = OFF")
    try:
        await db.executescript(
            """
            DROP TABLE IF EXISTS questions_new;
            CREATE TABLE questions_new (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL DEFAULT 'manifold',
                source_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                question_text_ru TEXT,
                category TEXT NOT NULL,
                subcategory TEXT,
                tags TEXT DEFAULT '[]',
                market_prob REAL,
                close_time TEXT,
                volume REAL,
                url TEXT,
                is_resolved INTEGER DEFAULT 0,
                resolution TEXT,
                resolution_time TEXT,
                fetched_at TEXT DEFAULT (datetime('now')),
                UNIQUE(source, source_id)
            );
            INSERT INTO questions_new (
                id, source, source_id, question_text, question_text_ru,
                category, subcategory, tags, market_prob, close_time,
                volume, url, is_resolved, resolution, resolution_time, fetched_at
            )
            SELECT
                id, 'manifold', manifold_id, question_text, question_text_ru,
                category, subcategory, tags, market_prob, close_time,
                volume, url, is_resolved, resolution, resolution_time, fetched_at
            FROM questions;
            DROP TABLE questions;
            ALTER TABLE questions_new RENAME TO questions;
            PRAGMA user_version = 1;
            """
        )
    finally:
        await db.execute("PRAGMA foreign_keys = ON")

    logger.info("Migrated questions table to multi-source schema")


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

        await _migrate_to_multi_source(db)
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

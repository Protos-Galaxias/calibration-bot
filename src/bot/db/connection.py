import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import aiosqlite

from bot.config import settings

logger = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def init_db() -> None:
    path = Path(settings.database_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(str(path)) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")

        schema = _SCHEMA_PATH.read_text()
        await db.executescript(schema)
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

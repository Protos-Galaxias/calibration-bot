from bot.db.connection import get_db


async def record_skip(user_id: int, category: str) -> None:
    async with get_db() as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO skipped_categories (user_id, category)
            VALUES (?, ?)
            """,
            (user_id, category),
        )

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


async def record_skipped_question(user_id: int, question_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO skipped_questions (user_id, question_id)
            VALUES (?, ?)
            """,
            (user_id, question_id),
        )

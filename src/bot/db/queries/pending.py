from bot.db.connection import get_db


async def set_pending_question(telegram_id: int, question_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO pending_questions (telegram_id, question_id)
            VALUES (?, ?)
            """,
            (telegram_id, question_id),
        )


async def get_pending_question_id(telegram_id: int) -> int | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT question_id FROM pending_questions WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = await cursor.fetchone()

        return row[0] if row else None


async def clear_pending_question(telegram_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "DELETE FROM pending_questions WHERE telegram_id = ?",
            (telegram_id,),
        )


async def has_pending_question(telegram_id: int) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT 1 FROM pending_questions WHERE telegram_id = ?",
            (telegram_id,),
        )

        return await cursor.fetchone() is not None

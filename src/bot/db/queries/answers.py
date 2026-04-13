from aiosqlite import Row

from bot.db.connection import get_db


async def create_answer(user_id: int, question_id: int, user_prob: float, market_prob: float) -> Row:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO answers (user_id, question_id, user_prob, market_prob_at_answer)
            VALUES (?, ?, ?, ?)
            RETURNING *
            """,
            (user_id, question_id, user_prob, market_prob),
        )
        row = await cursor.fetchone()

        return row  # type: ignore[return-value]


async def get_answers_for_question(question_id: int) -> list[Row]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM answers WHERE question_id = ?",
            (question_id,),
        )

        return await cursor.fetchall()  # type: ignore[return-value]


async def count_answers_today(user_id: int, today_iso: str) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM answers WHERE user_id = ? AND date(answered_at) = ?",
            (user_id, today_iso),
        )
        row = await cursor.fetchone()

        return row[0] if row else 0  # type: ignore[index]

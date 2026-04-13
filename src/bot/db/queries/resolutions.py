from aiosqlite import Row

from bot.db.connection import get_db


async def create_resolution(answer_id: int, outcome: int, user_brier: float, market_brier: float) -> Row:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO resolutions (answer_id, outcome, user_brier, market_brier)
            VALUES (?, ?, ?, ?)
            RETURNING *
            """,
            (answer_id, outcome, user_brier, market_brier),
        )
        row = await cursor.fetchone()

        return row  # type: ignore[return-value]


async def get_user_resolutions(user_id: int) -> list[Row]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT r.*, a.user_prob, a.market_prob_at_answer, q.category, q.question_text
            FROM resolutions r
            JOIN answers a ON a.id = r.answer_id
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ?
            ORDER BY r.resolved_at DESC
            """,
            (user_id,),
        )

        return await cursor.fetchall()  # type: ignore[return-value]


async def get_user_resolutions_since(user_id: int, since_iso: str) -> list[Row]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT r.*, a.user_prob, a.market_prob_at_answer, q.category, q.question_text
            FROM resolutions r
            JOIN answers a ON a.id = r.answer_id
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ? AND r.resolved_at >= ?
            ORDER BY r.resolved_at DESC
            """,
            (user_id, since_iso),
        )

        return await cursor.fetchall()  # type: ignore[return-value]


async def get_user_resolutions_by_category(user_id: int) -> list[Row]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT q.category,
                   COUNT(*) as cnt,
                   AVG(r.user_brier) as avg_user_brier,
                   AVG(r.market_brier) as avg_market_brier
            FROM resolutions r
            JOIN answers a ON a.id = r.answer_id
            JOIN questions q ON q.id = a.question_id
            WHERE a.user_id = ?
            GROUP BY q.category
            ORDER BY cnt DESC
            """,
            (user_id,),
        )

        return await cursor.fetchall()  # type: ignore[return-value]


async def count_user_resolutions(user_id: int) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM resolutions r
            JOIN answers a ON a.id = r.answer_id
            WHERE a.user_id = ?
            """,
            (user_id,),
        )
        row = await cursor.fetchone()

        return row[0] if row else 0  # type: ignore[index]


async def resolution_exists(answer_id: int) -> bool:
    async with get_db() as db:
        cursor = await db.execute("SELECT 1 FROM resolutions WHERE answer_id = ?", (answer_id,))

        return await cursor.fetchone() is not None

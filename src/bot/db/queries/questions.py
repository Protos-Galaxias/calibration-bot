from aiosqlite import Row

from bot.db.connection import get_db


async def upsert_question(
    manifold_id: str,
    question_text: str,
    category: str,
    market_prob: float,
    close_time: str,
    volume: float,
    url: str,
) -> Row:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO questions (manifold_id, question_text, category, market_prob, close_time, volume, url)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(manifold_id) DO UPDATE SET
                market_prob = excluded.market_prob,
                volume = excluded.volume
            RETURNING *
            """,
            (manifold_id, question_text, category, market_prob, close_time, volume, url),
        )
        row = await cursor.fetchone()

        return row  # type: ignore[return-value]


async def get_unused_question_for_user(user_id: int, category: str) -> Row | None:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT q.* FROM questions q
            WHERE q.category = ?
              AND q.is_resolved = 0
              AND q.id NOT IN (SELECT question_id FROM answers WHERE user_id = ?)
            ORDER BY RANDOM()
            LIMIT 1
            """,
            (category, user_id),
        )

        return await cursor.fetchone()


async def get_unresolved_with_answers() -> list[Row]:
    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT DISTINCT q.* FROM questions q
            JOIN answers a ON a.question_id = q.id
            WHERE q.is_resolved = 0
            """
        )

        return await cursor.fetchall()  # type: ignore[return-value]


async def mark_resolved(question_id: int, resolution: str, resolution_time: str) -> None:
    async with get_db() as db:
        await db.execute(
            """
            UPDATE questions SET is_resolved = 1, resolution = ?, resolution_time = ?
            WHERE id = ?
            """,
            (resolution, resolution_time, question_id),
        )


async def get_question_by_id(question_id: int) -> Row | None:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM questions WHERE id = ?", (question_id,))

        return await cursor.fetchone()


async def count_cached_by_category(category: str) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM questions WHERE category = ? AND is_resolved = 0",
            (category,),
        )
        row = await cursor.fetchone()

        return row[0] if row else 0  # type: ignore[index]


async def question_exists(manifold_id: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT 1 FROM questions WHERE manifold_id = ?",
            (manifold_id,),
        )

        return await cursor.fetchone() is not None

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
    tags: str = "[]",
    subcategory: str | None = None,
) -> Row:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO questions (manifold_id, question_text, category, subcategory, tags, market_prob, close_time, volume, url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(manifold_id) DO UPDATE SET
                market_prob = excluded.market_prob,
                volume = excluded.volume,
                tags = excluded.tags,
                subcategory = COALESCE(excluded.subcategory, questions.subcategory)
            RETURNING *
            """,
            (manifold_id, question_text, category, subcategory, tags, market_prob, close_time, volume, url),
        )
        row = await cursor.fetchone()

        return row  # type: ignore[return-value]


async def update_tags(question_id: int, tags_json: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE questions SET tags = ? WHERE id = ?",
            (tags_json, question_id),
        )


async def set_translation(question_id: int, text_ru: str) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE questions SET question_text_ru = ? WHERE id = ?",
            (text_ru, question_id),
        )


async def get_unused_question_for_user(user_id: int, subcategory: str) -> Row | None:
    """Get a random unresolved question the user hasn't answered or skipped.

    Matches by subcategory first; falls back to parent category for old
    questions that don't have a subcategory assigned yet.
    Skips questions whose close_time has already passed.
    """
    rows = await get_unused_questions_for_user(user_id, subcategory, limit=1)

    return rows[0] if rows else None


async def get_unused_questions_for_user(user_id: int, subcategory: str, *, limit: int = 20) -> list[Row]:
    """Get unresolved questions the user hasn't answered or skipped."""
    if limit <= 0:
        raise ValueError("limit must be positive")

    from bot.models.user import parent_category

    parent = parent_category(subcategory)

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT q.* FROM questions q
            WHERE (q.subcategory = ? OR (q.subcategory IS NULL AND q.category = ?))
              AND q.is_resolved = 0
              AND (q.close_time IS NULL OR datetime(q.close_time) > datetime('now'))
              AND NOT EXISTS (
                  SELECT 1 FROM answers a
                  WHERE a.question_id = q.id AND a.user_id = ?
              )
              AND NOT EXISTS (
                  SELECT 1 FROM skipped_questions sq
                  WHERE sq.question_id = q.id AND sq.user_id = ?
              )
            ORDER BY datetime(q.close_time) ASC
            LIMIT ?
            """,
            (subcategory, parent, user_id, user_id, limit),
        )

        return await cursor.fetchall()  # type: ignore[return-value]


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


async def count_cached_by_subcategory(subcategory: str) -> int:
    from bot.models.user import parent_category

    parent = parent_category(subcategory)

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM questions WHERE (subcategory = ? OR (subcategory IS NULL AND category = ?)) AND is_resolved = 0",
            (subcategory, parent),
        )
        row = await cursor.fetchone()

        return row[0] if row else 0  # type: ignore[index]


async def count_usable_cached_by_subcategory_for_user(user_id: int, subcategory: str) -> int:
    from bot.models.user import parent_category

    parent = parent_category(subcategory)

    async with get_db() as db:
        cursor = await db.execute(
            """
            SELECT COUNT(*) FROM questions q
            WHERE (q.subcategory = ? OR (q.subcategory IS NULL AND q.category = ?))
              AND q.is_resolved = 0
              AND (q.close_time IS NULL OR datetime(q.close_time) > datetime('now'))
              AND NOT EXISTS (
                  SELECT 1 FROM answers a
                  WHERE a.question_id = q.id AND a.user_id = ?
              )
              AND NOT EXISTS (
                  SELECT 1 FROM skipped_questions sq
                  WHERE sq.question_id = q.id AND sq.user_id = ?
              )
            """,
            (subcategory, parent, user_id, user_id),
        )
        row = await cursor.fetchone()

        return row[0] if row else 0  # type: ignore[index]


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

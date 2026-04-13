import json

from aiosqlite import Row

from bot.db.connection import get_db


async def create_user(telegram_id: int, categories: list[str], timezone: str, daily_hour: int) -> Row:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO users (telegram_id, categories, timezone, daily_hour)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                categories = excluded.categories,
                timezone = excluded.timezone,
                daily_hour = excluded.daily_hour
            RETURNING *
            """,
            (telegram_id, json.dumps(categories), timezone, daily_hour),
        )
        row = await cursor.fetchone()

        return row  # type: ignore[return-value]


async def get_user(telegram_id: int) -> Row | None:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))

        return await cursor.fetchone()


async def get_user_by_id(user_id: int) -> Row | None:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))

        return await cursor.fetchone()


async def get_all_users() -> list[Row]:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users")

        return await cursor.fetchall()  # type: ignore[return-value]


async def update_user_categories(telegram_id: int, categories: list[str]) -> None:
    async with get_db() as db:
        await db.execute(
            "UPDATE users SET categories = ? WHERE telegram_id = ?",
            (json.dumps(categories), telegram_id),
        )


async def update_user_settings(telegram_id: int, *, timezone: str | None = None, daily_hour: int | None = None) -> None:
    parts: list[str] = []
    params: list[object] = []

    if timezone is not None:
        parts.append("timezone = ?")
        params.append(timezone)
    if daily_hour is not None:
        parts.append("daily_hour = ?")
        params.append(daily_hour)

    if not parts:
        return

    params.append(telegram_id)
    async with get_db() as db:
        await db.execute(
            f"UPDATE users SET {', '.join(parts)} WHERE telegram_id = ?",
            params,
        )


async def increment_answers(user_id: int) -> Row:
    async with get_db() as db:
        cursor = await db.execute(
            """
            UPDATE users SET total_answers = total_answers + 1
            WHERE id = ?
            RETURNING *
            """,
            (user_id,),
        )
        row = await cursor.fetchone()

        return row  # type: ignore[return-value]


async def update_streak(user_id: int, today_iso: str) -> Row:
    async with get_db() as db:
        user_cur = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = await user_cur.fetchone()
        if not user:
            raise ValueError(f"User {user_id} not found")

        last_date = user["streak_last_date"]
        current = user["streak_current"]

        if last_date == today_iso:
            return user

        from datetime import date, timedelta

        if last_date and date.fromisoformat(last_date) == date.fromisoformat(today_iso) - timedelta(days=1):
            new_current = current + 1
        else:
            new_current = 1

        new_best = max(user["streak_best"], new_current)

        cursor = await db.execute(
            """
            UPDATE users SET streak_current = ?, streak_best = ?, streak_last_date = ?
            WHERE id = ?
            RETURNING *
            """,
            (new_current, new_best, today_iso, user_id),
        )
        row = await cursor.fetchone()

        return row  # type: ignore[return-value]


async def update_phase(user_id: int, phase: str) -> None:
    async with get_db() as db:
        await db.execute("UPDATE users SET phase = ? WHERE id = ?", (phase, user_id))

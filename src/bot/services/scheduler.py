import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


async def _send_daily_questions() -> None:
    from bot.db.queries.users import get_all_users
    from bot.handlers.question import send_question_to_user
    from bot.main import manifold_client
    from bot.services.question_picker import pick_question

    users = await get_all_users()

    for user in users:
        try:
            user_tz = ZoneInfo(user["timezone"])
            user_now = datetime.now(user_tz)
            if user_now.hour != user["daily_hour"]:
                continue

            question = await pick_question(user, manifold_client)
            if not question:
                continue

            await send_question_to_user(user["telegram_id"], user, question)
        except Exception:
            logger.exception("Failed to send daily question to user %s", user["telegram_id"])


async def _check_resolutions() -> None:
    from bot.main import bot, manifold_client
    from bot.services.resolution import check_resolutions
    from bot.helpers.formatting import format_resolution
    from bot.db.queries.users import get_user_by_id

    notifications = await check_resolutions(manifold_client, bot)

    for n in notifications:
        try:
            user = await get_user_by_id(n["user_id"])
            if not user:
                continue

            text = format_resolution(
                question_text=n["question_text"],
                resolution=n["resolution"],
                user_prob=n["user_prob"],
                market_prob=n["market_prob"],
                user_brier=n["user_brier"],
                market_brier=n["market_brier"],
            )
            await bot.send_message(user["telegram_id"], text, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send resolution to user %s", n["user_id"])


async def _send_weekly_summary() -> None:
    from bot.db.queries.answers import count_answers_today
    from bot.db.queries.resolutions import count_user_resolutions
    from bot.db.queries.users import get_all_users
    from bot.helpers.formatting import format_weekly_summary
    from bot.main import bot
    from bot.services.scoring import get_rolling_brier

    users = await get_all_users()

    for user in users:
        try:
            user_id = user["id"]
            created = datetime.fromisoformat(user["created_at"])
            weeks = max(1, (datetime.now(timezone.utc) - created.replace(tzinfo=timezone.utc)).days // 7)

            resolutions = await count_user_resolutions(user_id)
            brier_now = await get_rolling_brier(user_id, days=30)
            brier_prev = await get_rolling_brier(user_id, days=60)

            text = format_weekly_summary(
                week_num=weeks,
                questions_count=user["total_answers"],
                resolutions_count=resolutions,
                brier_prev=brier_prev,
                brier_now=brier_now,
                streak=user["streak_current"],
            )
            await bot.send_message(user["telegram_id"], text, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send weekly summary to user %s", user["telegram_id"])


async def setup_scheduler() -> AsyncScheduler:
    scheduler = AsyncScheduler()

    await scheduler.add_schedule(
        _send_daily_questions,
        CronTrigger(minute=0),
        id="daily_questions",
    )

    await scheduler.add_schedule(
        _check_resolutions,
        IntervalTrigger(hours=1),
        id="check_resolutions",
    )

    await scheduler.add_schedule(
        _send_weekly_summary,
        CronTrigger(day_of_week="mon", hour=10, minute=0),
        id="weekly_summary",
    )

    return scheduler

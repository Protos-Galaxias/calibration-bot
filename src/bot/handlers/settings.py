import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router, types
from aiogram.filters import Command

from bot.db.queries.users import get_user, update_user_categories, update_user_settings
from bot.models.user import ALL_CATEGORY_SLUGS, CATEGORIES

logger = logging.getLogger(__name__)
router = Router()

TIMEZONES = [
    "Europe/Kaliningrad",
    "Europe/Moscow",
    "Europe/Samara",
    "Asia/Yekaterinburg",
    "Asia/Omsk",
    "Asia/Krasnoyarsk",
    "Asia/Irkutsk",
    "Asia/Yakutsk",
    "Asia/Vladivostok",
    "Asia/Magadan",
    "Asia/Kamchatka",
    "Europe/London",
    "Europe/Berlin",
    "US/Eastern",
    "US/Pacific",
]


def _tz_label(tz_name: str) -> str:
    now = datetime.now(ZoneInfo(tz_name))
    offset = now.strftime("%z")
    sign = offset[0]
    hours = offset[1:3].lstrip("0") or "0"

    return f"{tz_name} (UTC{sign}{hours})"


def _settings_keyboard(user_categories: list[str], daily_hour: int, timezone: str) -> types.InlineKeyboardMarkup:
    rows: list[list[types.InlineKeyboardButton]] = []

    rows.append([types.InlineKeyboardButton(
        text=f"⏰ Время вопроса: {daily_hour}:00",
        callback_data="settings:noop",
    )])

    rows.append([types.InlineKeyboardButton(
        text=f"🌍 {_tz_label(timezone)}",
        callback_data="settings:noop",
    )])

    for slug, label in CATEGORIES.items():
        check = "✅" if slug in user_categories else "⬜"
        rows.append([types.InlineKeyboardButton(
            text=f"{check} {label}",
            callback_data=f"settings_cat:{slug}",
        )])

    rows.append([
        types.InlineKeyboardButton(text="⏰ −1ч", callback_data="settings_hour:dec"),
        types.InlineKeyboardButton(text="⏰ +1ч", callback_data="settings_hour:inc"),
    ])

    rows.append([
        types.InlineKeyboardButton(text="🌍 ←", callback_data="settings_tz:prev"),
        types.InlineKeyboardButton(text="🌍 →", callback_data="settings_tz:next"),
    ])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("settings"))
async def cmd_settings(message: types.Message) -> None:
    if not message.from_user:
        return

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запустите бота командой /start")

        return

    cats = json.loads(user["categories"])
    kb = _settings_keyboard(cats, user["daily_hour"], user["timezone"])
    await message.answer("⚙️ <b>Настройки</b>", parse_mode="HTML", reply_markup=kb)


@router.callback_query(lambda c: c.data and c.data.startswith("settings_cat:"))
async def on_settings_cat(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    slug = callback.data.split(":")[1]
    user = await get_user(callback.from_user.id)
    if not user:
        return

    cats: list[str] = json.loads(user["categories"])
    if slug in cats:
        if len(cats) <= 2:
            await callback.answer("Минимум 2 категории!", show_alert=True)

            return
        cats.remove(slug)
    else:
        cats.append(slug)

    await update_user_categories(callback.from_user.id, cats)
    kb = _settings_keyboard(cats, user["daily_hour"], user["timezone"])
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("settings_hour:"))
async def on_settings_hour(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    user = await get_user(callback.from_user.id)
    if not user:
        return

    direction = callback.data.split(":")[1]
    hour = user["daily_hour"]
    if direction == "inc":
        hour = (hour + 1) % 24
    else:
        hour = (hour - 1) % 24

    await update_user_settings(callback.from_user.id, daily_hour=hour)
    cats = json.loads(user["categories"])
    kb = _settings_keyboard(cats, hour, user["timezone"])
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(f"Время вопроса: {hour}:00")


@router.callback_query(lambda c: c.data and c.data.startswith("settings_tz:"))
async def on_settings_tz(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    user = await get_user(callback.from_user.id)
    if not user:
        return

    current_tz = user["timezone"]
    try:
        idx = TIMEZONES.index(current_tz)
    except ValueError:
        idx = 0

    direction = callback.data.split(":")[1]
    if direction == "next":
        idx = (idx + 1) % len(TIMEZONES)
    else:
        idx = (idx - 1) % len(TIMEZONES)

    new_tz = TIMEZONES[idx]
    await update_user_settings(callback.from_user.id, timezone=new_tz)
    cats = json.loads(user["categories"])
    kb = _settings_keyboard(cats, user["daily_hour"], new_tz)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(f"Таймзона: {_tz_label(new_tz)}")

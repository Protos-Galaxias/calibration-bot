import json
import logging

from aiogram import Router, types
from aiogram.filters import CommandStart

from bot.config import settings
from bot.db.queries.users import create_user, get_user
from bot.models.user import ALL_SUBCATEGORY_SLUGS, SUBCATEGORIES
from bot.services.question_picker import pick_question

logger = logging.getLogger(__name__)
router = Router()

WELCOME_TEXT = (
    "👋 <b>Привет! Я — Calibration Bot.</b>\n\n"
    "Я помогу тебе тренировать точность прогнозов. Каждый день я буду "
    "присылать вопрос из реального мира — ты оцениваешь вероятность, "
    "а когда событие наступает, мы сверяем прогноз с реальностью.\n\n"
    "Основная метрика — <b>Brier Score</b> (0 = идеал, 1 = максимальная ошибка). "
    "Средний человек: ~0.3, хороший прогнозист: ~0.15–0.2.\n\n"
    "Первые 50 вопросов — фаза калибровки. После неё я узнаю твои сильные "
    "и слабые стороны и начну давать персонализированную аналитику."
)

CATEGORIES_TEXT = (
    "Выбери подкатегории, которые тебе интересны (минимум 2).\n"
    "Нажми на подкатегорию, чтобы включить/выключить её, затем нажми «Готово»."
)


def _build_keyboard(selected: set[str]) -> types.InlineKeyboardMarkup:
    rows: list[list[types.InlineKeyboardButton]] = []
    for parent_slug, grp in SUBCATEGORIES.items():
        if not grp["children"]:
            check = "✅" if parent_slug in selected else "⬜"
            rows.append([types.InlineKeyboardButton(
                text=f"{check} {grp['icon']} {grp['label']}",
                callback_data=f"cat_toggle:{parent_slug}",
            )])
            continue

        rows.append([types.InlineKeyboardButton(
            text=f"── {grp['icon']} {grp['label']} ──",
            callback_data="cat_noop",
        )])
        for sub_slug, sub_label in grp["children"].items():
            check = "✅" if sub_slug in selected else "⬜"
            rows.append([types.InlineKeyboardButton(
                text=f"  {check} {sub_label}",
                callback_data=f"cat_toggle:{sub_slug}",
            )])

    rows.append([
        types.InlineKeyboardButton(text="✔️ Готово", callback_data="cat_done"),
    ])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


def _all_slugs() -> set[str]:
    """All selectable slugs: subcategories + parentless categories like misc."""
    result = set(ALL_SUBCATEGORY_SLUGS)
    for slug, grp in SUBCATEGORIES.items():
        if not grp["children"]:
            result.add(slug)

    return result


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    if not message.from_user:
        return

    existing = await get_user(message.from_user.id)
    if existing:
        await message.answer("Ты уже зарегистрирован(а). Используй /question для нового вопроса или /help для справки.")

        return

    await message.answer(WELCOME_TEXT, parse_mode="HTML")

    selected = _all_slugs()
    kb = _build_keyboard(selected)
    await message.answer(CATEGORIES_TEXT, reply_markup=kb, parse_mode="HTML")


_user_selections: dict[int, set[str]] = {}


@router.callback_query(lambda c: c.data == "cat_noop")
async def on_cat_noop(callback: types.CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("cat_toggle:"))
async def on_cat_toggle(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    slug = callback.data.split(":")[1]
    uid = callback.from_user.id

    if uid not in _user_selections:
        _user_selections[uid] = _all_slugs()

    sel = _user_selections[uid]
    if slug in sel:
        sel.discard(slug)
    else:
        sel.add(slug)

    kb = _build_keyboard(sel)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data == "cat_done")
async def on_cat_done(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.message:
        return

    uid = callback.from_user.id
    sel = _user_selections.pop(uid, _all_slugs())

    if len(sel) < 2:
        await callback.answer("Выбери минимум 2 подкатегории!", show_alert=True)
        _user_selections[uid] = sel

        return

    all_ordered = list(_all_slugs())
    categories = [s for s in all_ordered if s in sel]

    user_row = await create_user(
        telegram_id=uid,
        categories=categories,
        timezone=settings.timezone_default,
        daily_hour=settings.daily_question_default_hour,
    )

    await callback.message.edit_text("✅ Отлично! Подкатегории сохранены. Сейчас пришлю первый вопрос...")
    await callback.answer()

    from bot.main import manifold_client
    question = await pick_question(user_row, manifold_client)
    if not question:
        await callback.message.answer("К сожалению, сейчас нет подходящих вопросов. Попробуй позже через /question.")

        return

    from bot.handlers.question import send_question_to_user

    await send_question_to_user(callback.message.chat.id, user_row, question)

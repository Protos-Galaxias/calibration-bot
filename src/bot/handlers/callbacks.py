import json
import logging

from aiogram import Router, types

from bot.db.queries.pending import clear_pending_question, get_pending_question_id
from bot.db.queries.questions import get_question_by_id
from bot.db.queries.skipped import record_skip
from bot.db.queries.users import add_blocked_tag, get_blocked_tags, get_user, remove_blocked_tag, update_user_categories
from bot.models.user import CATEGORIES

logger = logging.getLogger(__name__)
router = Router()

IGNORED_TAGS = frozenset({
    "manifold", "manifold-markets", "fun", "personal", "world",
    "sort-by-close-date", "sort-by-newest",
})


def _tag_label(tag: str) -> str:
    return tag.replace("-", " ").title()


def _meaningful_tags(raw_tags: str | None) -> list[str]:
    tags = json.loads(raw_tags or "[]")

    return [t for t in tags if t.lower() not in IGNORED_TAGS][:6]


def _block_tags_keyboard(tags: list[str]) -> types.InlineKeyboardMarkup | None:
    if not tags:
        return None
    rows = []
    for tag in tags:
        rows.append([types.InlineKeyboardButton(
            text=f"🚫 {_tag_label(tag)}",
            callback_data=f"block_tag:{tag}",
        )])
    rows.append([types.InlineKeyboardButton(
        text="➡️ Просто следующий вопрос",
        callback_data="block_tag:__skip__",
    )])

    return types.InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(lambda c: c.data and c.data.startswith("skip_topic:"))
async def on_skip_topic(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    category = callback.data.split(":")[1]
    tg_id = callback.from_user.id

    q_id = await get_pending_question_id(tg_id)
    await clear_pending_question(tg_id)

    user = await get_user(tg_id)
    if not user:
        return

    await record_skip(user["id"], category)

    question_tags: list[str] = []
    if q_id:
        q_row = await get_question_by_id(q_id)
        if q_row:
            raw = q_row["tags"] if "tags" in q_row.keys() else "[]"
            question_tags = _meaningful_tags(raw)

    tag_kb = _block_tags_keyboard(question_tags)
    if tag_kb:
        await callback.message.edit_text(
            "⏭ Вопрос пропущен.\n\nХочешь заблокировать какой-нибудь тег? "
            "Вопросы с заблокированным тегом больше не будут приходить.",
            reply_markup=tag_kb,
        )
    else:
        await callback.message.edit_text("⏭ Вопрос пропущен.")
        await _send_next(callback, user)

    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("block_tag:"))
async def on_block_tag(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    tag = callback.data.split(":", 1)[1]
    tg_id = callback.from_user.id

    user = await get_user(tg_id)
    if not user:
        return

    if tag == "__skip__":
        await callback.message.edit_text("⏭ Вопрос пропущен.")
    else:
        await add_blocked_tag(tg_id, tag)
        await callback.message.edit_text(
            f"🚫 Тег <b>{_tag_label(tag)}</b> заблокирован.\n"
            f"Управлять тегами можно в /settings → 🏷 Заблокированные теги.",
            parse_mode="HTML",
        )

    await callback.answer()
    await _send_next(callback, user)


@router.callback_query(lambda c: c.data and c.data.startswith("unblock_tag:"))
async def on_unblock_tag(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    tag = callback.data.split(":", 1)[1]
    tg_id = callback.from_user.id

    await remove_blocked_tag(tg_id, tag)

    blocked = await get_blocked_tags(tg_id)
    if blocked:
        rows = []
        for t in blocked:
            rows.append([types.InlineKeyboardButton(
                text=f"❌ {_tag_label(t)}",
                callback_data=f"unblock_tag:{t}",
            )])
        rows.append([types.InlineKeyboardButton(text="⬅️ Назад", callback_data="settings:back")])
        kb = types.InlineKeyboardMarkup(inline_keyboard=rows)
        await callback.message.edit_text(
            "🏷 <b>Заблокированные теги</b>\nНажми, чтобы разблокировать:",
            parse_mode="HTML",
            reply_markup=kb,
        )
    else:
        await callback.message.edit_text("🏷 Все теги разблокированы.")

    await callback.answer()


async def _send_next(callback: types.CallbackQuery, user) -> None:
    if not callback.message:
        return

    from bot.main import manifold_client
    from bot.services.question_picker import pick_question

    question = await pick_question(user, manifold_client)
    if question:
        from bot.handlers.question import send_question_to_user
        await send_question_to_user(callback.message.chat.id, user, question)

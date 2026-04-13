import json
import logging

from aiogram import Router, types

from bot.db.queries.pending import clear_pending_question
from bot.db.queries.skipped import record_skip
from bot.db.queries.users import get_user, update_user_categories
from bot.models.user import CATEGORIES

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("skip_topic:"))
async def on_skip_topic(callback: types.CallbackQuery) -> None:
    if not callback.from_user or not callback.data or not callback.message:
        return

    category = callback.data.split(":")[1]
    tg_id = callback.from_user.id

    await clear_pending_question(tg_id)

    user = await get_user(tg_id)
    if not user:
        return

    await record_skip(user["id"], category)

    cats: list[str] = json.loads(user["categories"])
    if category in cats and len(cats) > 2:
        cats.remove(category)
        await update_user_categories(tg_id, cats)
        cat_label = CATEGORIES.get(category, category)
        await callback.message.edit_text(
            f"⏭ Категория {cat_label} отключена. Включить обратно можно в /settings."
        )
    else:
        await callback.message.edit_text("⏭ Вопрос пропущен.")

    await callback.answer()

    from bot.main import manifold_client
    from bot.services.question_picker import pick_question

    question = await pick_question(user, manifold_client)
    if question:
        from bot.handlers.question import send_question_to_user
        await send_question_to_user(callback.message.chat.id, user, question)

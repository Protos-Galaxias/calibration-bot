import json
import logging

from aiogram import Bot, Router, types
from aiogram.filters import Command

from bot.db.queries.pending import has_pending_question, set_pending_question
from bot.db.queries.questions import set_translation, update_tags
from bot.db.queries.users import get_user
from bot.helpers.formatting import format_question_message
from bot.services.translator import translate_to_russian

logger = logging.getLogger(__name__)
router = Router()


async def _fetch_tags_from_source(source_name: str, source_id: str, question_id: int) -> list[str]:
    from bot.main import sources_registry

    source = sources_registry.get(source_name)
    if not source:
        logger.warning("No registered source %r for question %d", source_name, question_id)

        return []

    try:
        market = await source.get_market(source_id)
    except Exception:
        logger.warning("Failed to fetch tags for %s/%s", source_name, source_id)

        return []

    if not market or not market.tags:
        return []

    await update_tags(question_id, json.dumps(market.tags))

    return market.tags


def _skip_button(category: str) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⏭ Пропустить тему", callback_data=f"skip_topic:{category}")]
    ])


async def send_question_to_user(chat_id: int, user_row, question_row) -> None:
    from bot.main import bot

    question_text = question_row["question_text"]
    text_ru = question_row["question_text_ru"] if "question_text_ru" in question_row.keys() else None

    if not text_ru:
        text_ru = await translate_to_russian(question_text)
        if text_ru:
            await set_translation(question_row["id"], text_ru)

    raw_tags = question_row["tags"] if "tags" in question_row.keys() else "[]"
    tags: list[str] = json.loads(raw_tags) if raw_tags else []

    if not tags:
        source_name = question_row["source"] if "source" in question_row.keys() and question_row["source"] else "manifold"
        tags = await _fetch_tags_from_source(source_name, question_row["source_id"], question_row["id"])

    subcategory = question_row["subcategory"] if "subcategory" in question_row.keys() else None

    text = format_question_message(
        question_text=question_text,
        category=question_row["category"],
        total_answers=user_row["total_answers"],
        phase=user_row["phase"],
        question_text_ru=text_ru,
        tags=tags,
        subcategory=subcategory,
    )
    kb = _skip_button(question_row["category"])
    await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

    await set_pending_question(user_row["telegram_id"], question_row["id"])


@router.message(Command("question"))
async def cmd_question(message: types.Message) -> None:
    if not message.from_user:
        return

    user = await get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала запустите бота командой /start")

        return

    if await has_pending_question(message.from_user.id):
        await message.answer("У тебя уже есть неотвеченный вопрос. Ответь числом от 0 до 100.")

        return

    from bot.main import sources_registry
    from bot.services.question_picker import pick_question

    question = await pick_question(user, sources_registry)
    if not question:
        await message.answer("Сейчас нет подходящих вопросов. Попробуй позже.")

        return

    await send_question_to_user(message.chat.id, user, question)

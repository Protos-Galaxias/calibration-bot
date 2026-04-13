import logging
from datetime import date

from aiogram import Bot, Router, types
from aiogram.filters import Command

from bot.db.queries.answers import count_answers_today
from bot.db.queries.pending import has_pending_question, set_pending_question
from bot.db.queries.users import get_user
from bot.helpers.formatting import format_question_message

logger = logging.getLogger(__name__)
router = Router()

CALIBRATION_LIMIT = 5
POST_CALIBRATION_LIMIT = 3


def _skip_button(category: str) -> types.InlineKeyboardMarkup:
    return types.InlineKeyboardMarkup(inline_keyboard=[
        [types.InlineKeyboardButton(text="⏭ Пропустить тему", callback_data=f"skip_topic:{category}")]
    ])


async def send_question_to_user(chat_id: int, user_row, question_row) -> None:
    from bot.main import bot

    text = format_question_message(
        question_text=question_row["question_text"],
        category=question_row["category"],
        total_answers=user_row["total_answers"],
        phase=user_row["phase"],
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

    today = date.today().isoformat()
    answered_today = await count_answers_today(user["id"], today)
    limit = CALIBRATION_LIMIT if user["phase"] == "calibration" else POST_CALIBRATION_LIMIT

    if answered_today >= limit:
        await message.answer(f"Лимит на сегодня: {limit} вопросов. Приходи завтра!")

        return

    from bot.main import manifold_client
    from bot.services.question_picker import pick_question

    question = await pick_question(user, manifold_client)
    if not question:
        await message.answer("Сейчас нет подходящих вопросов. Попробуй позже.")

        return

    await send_question_to_user(message.chat.id, user, question)

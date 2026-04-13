from bot.models.user import CATEGORIES

CALIBRATION_GOAL = 50


def category_label(slug: str) -> str:
    return CATEGORIES.get(slug, slug)


def format_question_message(
    question_text: str,
    category: str,
    total_answers: int,
    phase: str,
) -> str:
    counter = f"Калибровка: {total_answers}/{CALIBRATION_GOAL}" if phase == "calibration" else f"Прогнозов: {total_answers}"
    cat = category_label(category)

    return (
        f"🔮 <b>Вопрос дня</b> · {counter}\n\n"
        f"📁 {cat}\n\n"
        f"{question_text}\n\n"
        f"Рыночная вероятность (Manifold): скрыта до твоего ответа.\n\n"
        f"С какой вероятностью это произойдёт? (0–100%)"
    )


def format_answer_response(user_prob: float, market_prob: float) -> str:
    u = int(user_prob * 100)
    m = int(market_prob * 100)
    diff = abs(u - m)

    return (
        f"📝 Твоя оценка: <b>{u}%</b>\n"
        f"📊 Рынок (Manifold): <b>{m}%</b>\n"
        f"📏 Расхождение: {diff} п.п."
    )


def format_resolution(
    question_text: str,
    resolution: str,
    user_prob: float,
    market_prob: float,
    user_brier: float,
    market_brier: float,
) -> str:
    icon = "✅" if resolution == "YES" else "❌"
    outcome_text = "Да" if resolution == "YES" else "Нет"
    u = int(user_prob * 100)
    m = int(market_prob * 100)

    return (
        f"{icon} <b>Резолюция</b>\n\n"
        f'"{question_text}" — <b>{outcome_text}.</b>\n\n'
        f"Твоя оценка: {u}% · Рынок: {m}%\n"
        f"Твой Brier: {user_brier:.2f} · Рыночный Brier: {market_brier:.2f}"
    )


def format_stats(
    total_answers: int,
    total_resolutions: int,
    overall_brier: float | None,
    rolling_brier: float | None,
    market_brier: float | None,
    streak_current: int,
    streak_best: int,
) -> str:
    lines = [
        "📊 <b>Твоя статистика</b>\n",
        f"Прогнозов: {total_answers} · Резолюций: {total_resolutions}",
    ]

    if overall_brier is not None:
        lines.append(f"Brier Score (общий): <b>{overall_brier:.3f}</b>")
    if rolling_brier is not None:
        lines.append(f"Brier Score (30 дней): <b>{rolling_brier:.3f}</b>")
    if market_brier is not None:
        lines.append(f"Brier рынка: <b>{market_brier:.3f}</b>")

    lines.append(f"\n🔥 Серия: {streak_current} дн. (лучшая: {streak_best})")

    return "\n".join(lines)


def format_domains(domains: list[dict]) -> str:
    if not domains:
        return "Пока нет резолюций по категориям."

    lines = ["📁 <b>Разбивка по категориям</b>\n"]
    for d in domains:
        cat = category_label(d["category"])
        edge = d["expert_edge"]
        edge_icon = "🔬" if edge < 0 else "⚠️"
        edge_text = f"{edge:+.3f}"
        lines.append(
            f"{cat}: Brier {d['user_brier']:.3f} "
            f"(рынок: {d['market_brier']:.3f}) · "
            f"Резолюций: {d['count']}"
        )
        if d["count"] >= 15:
            lines.append(f"  {edge_icon} Expert Edge: {edge_text}")

    return "\n".join(lines)


def format_weekly_summary(
    week_num: int,
    questions_count: int,
    resolutions_count: int,
    brier_prev: float | None,
    brier_now: float | None,
    streak: int,
) -> str:
    lines = [f"📊 <b>Неделя #{week_num}</b>\n"]
    lines.append(f"Вопросов: {questions_count} · Резолюций: {resolutions_count}")

    if brier_prev is not None and brier_now is not None:
        arrow = "📉" if brier_now < brier_prev else "📈"
        trend = "улучшение" if brier_now < brier_prev else "ухудшение"
        lines.append(f"Brier Score (30 дней): {brier_prev:.2f} → {brier_now:.2f} {arrow}")
        lines.append(f"Тренд: {trend}")
    elif brier_now is not None:
        lines.append(f"Brier Score (30 дней): {brier_now:.2f}")

    lines.append(f"\n🔥 Серия: {streak} дн.")

    return "\n".join(lines)


def format_calibration_complete(overall_brier: float, domains: list[dict]) -> str:
    lines = [
        "🎯 <b>Калибровка завершена!</b>\n",
        "Ты ответил(а) на 50 вопросов — теперь бот знает твой профиль.\n",
        f"Brier Score: <b>{overall_brier:.3f}</b>\n",
    ]

    if domains:
        lines.append("Разбивка по доменам:")
        for d in domains:
            cat = category_label(d["category"])
            lines.append(f"  {cat}: {d['user_brier']:.3f} ({d['count']} резолюций)")

    lines.append("\nТеперь бот будет адаптировать вопросы под твои сильные и слабые стороны.")

    return "\n".join(lines)

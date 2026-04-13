# Calibration Bot

Telegram-бот для тренировки калибровки вероятностных оценок. Бот присылает вопросы с prediction markets (Manifold Markets), собирает прогнозы пользователей, отслеживает резолюции и вычисляет Brier Score.

## Быстрый старт

```bash
# 1. Скопировать и заполнить конфиг
cp .env.example .env
# Заполнить TELEGRAM_BOT_TOKEN и ANTHROPIC_API_KEY

# 2. Запустить
docker compose up -d --build

# 3. Логи
docker compose logs -f bot
```

## Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Онбординг, выбор категорий |
| `/question` | Дополнительный вопрос |
| `/stats` | Brier Score, тренды |
| `/domains` | Точность по категориям |
| `/streak` | Серия ответов |
| `/settings` | Время, категории |
| `/help` | Справка |

## Архитектура

- **aiogram 3** — Telegram Bot API
- **aiosqlite** — SQLite с WAL mode
- **httpx** — Manifold Markets API
- **APScheduler 4** — ежедневные вопросы, часовая проверка резолюций, еженедельные сводки
- **OpenRouter** (опционально) — LLM-классификация вопросов, если теги не покрывают категорию

## Конфигурация (.env)

| Переменная | Описание |
|------------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram бота от @BotFather |
| `OPENROUTER_API_KEY` | API ключ OpenRouter (опционально, без него — fallback на "misc") |
| `OPENROUTER_MODEL` | Модель для классификации (default: `google/gemini-2.0-flash-001`) |
| `DATABASE_PATH` | Путь к SQLite файлу (default: `./data/calibration.db`) |
| `DAILY_QUESTION_DEFAULT_HOUR` | Час отправки ежедневного вопроса (default: 10) |
| `TIMEZONE_DEFAULT` | Часовой пояс по умолчанию (default: `Europe/Moscow`) |
| `LOG_LEVEL` | Уровень логирования (default: `INFO`) |

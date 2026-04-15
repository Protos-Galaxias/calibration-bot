CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    timezone TEXT DEFAULT 'Europe/Moscow',
    daily_hour INTEGER DEFAULT 10,
    categories TEXT NOT NULL,
    phase TEXT DEFAULT 'calibration',
    total_answers INTEGER DEFAULT 0,
    streak_current INTEGER DEFAULT 0,
    streak_best INTEGER DEFAULT 0,
    streak_last_date TEXT,
    blocked_tags TEXT DEFAULT '[]',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    manifold_id TEXT UNIQUE NOT NULL,
    question_text TEXT NOT NULL,
    question_text_ru TEXT,
    category TEXT NOT NULL,
    tags TEXT DEFAULT '[]',
    market_prob REAL,
    close_time TEXT,
    volume REAL,
    url TEXT,
    is_resolved INTEGER DEFAULT 0,
    resolution TEXT,
    resolution_time TEXT,
    fetched_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    question_id INTEGER REFERENCES questions(id),
    user_prob REAL NOT NULL,
    market_prob_at_answer REAL NOT NULL,
    answered_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, question_id)
);

CREATE TABLE IF NOT EXISTS resolutions (
    id INTEGER PRIMARY KEY,
    answer_id INTEGER UNIQUE REFERENCES answers(id),
    outcome INTEGER NOT NULL,
    user_brier REAL NOT NULL,
    market_brier REAL NOT NULL,
    resolved_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS skipped_categories (
    user_id INTEGER REFERENCES users(id),
    category TEXT NOT NULL,
    skipped_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY(user_id, category)
);

CREATE TABLE IF NOT EXISTS skipped_questions (
    user_id INTEGER REFERENCES users(id),
    question_id INTEGER REFERENCES questions(id),
    skipped_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY(user_id, question_id)
);

CREATE TABLE IF NOT EXISTS pending_questions (
    telegram_id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    created_at TEXT DEFAULT (datetime('now'))
);

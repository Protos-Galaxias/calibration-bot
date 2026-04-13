from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    telegram_bot_token: str
    openrouter_api_key: str = ""
    openrouter_model: str = "google/gemini-2.0-flash-001"
    database_path: str = "./data/calibration.db"
    daily_question_default_hour: int = 10
    timezone_default: str = "Europe/Moscow"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()  # type: ignore[call-arg]

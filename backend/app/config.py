from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str = ""
    groq_model: str = "qwen/qwen3.6-27b"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    database_url: str = "sqlite:///./dev.db"
    storage_backend: str = "local"
    upload_dir: str = "./uploads"
    s3_endpoint: str = ""
    s3_region: str = ""
    s3_bucket: str = ""
    s3_key: str = ""
    s3_secret: str = ""
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    frontend_origin: str = "http://localhost:5173"
    confidence_threshold: float = 0.8
    timezone: str = "Asia/Kolkata"
    retention_days: int = 30

    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

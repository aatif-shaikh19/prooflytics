from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal

class Settings(BaseSettings):
    APP_ENV: Literal["development", "production", "testing"] = "development"
    DATABASE_URL: str = "sqlite:///./prooflytics.db"
    SESSION_SECRET: str = "prooflytics-development-secret-change-in-production"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024  # 5 MiB
    COOKIE_SECURE: bool = False
    SESSION_COOKIE_NAME: str = "prooflytics_session"
    SESSION_MAX_AGE_DAYS: int = 7

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

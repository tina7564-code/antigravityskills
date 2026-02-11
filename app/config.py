from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'social-comment-monitor'
    environment: str = 'dev'

    database_url: str = Field(
        default='postgresql+asyncpg://postgres:postgres@localhost:5432/social_monitor'
    )
    redis_url: str = 'redis://localhost:6379/0'

    polling_interval_seconds: int = 15
    worker_concurrency: int = 4

    sentiment_provider: str = 'transformers'  # transformers | openai | mock
    openai_api_key: str | None = None
    openai_model: str = 'gpt-4o-mini'

    webhook_secret: str = 'change-me'

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    alert_email_to: str | None = None

    wecom_webhook_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

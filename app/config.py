"""Environment-backed application configuration."""

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and an optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    weather_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    anthropic_api_key: SecretStr = Field(default=SecretStr(""), repr=False)

    weather_base_url: str = "https://api.openweathermap.org/data/2.5/weather"
    joke_api_url: str = "https://v2.jokeapi.dev/joke/Any"
    anthropic_messages_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    external_timeout_seconds: float = Field(default=8.0, gt=0, le=60)
    max_summary_text_length: int = Field(default=5_000, ge=1, le=100_000)
    summary_max_words: int = Field(default=120, ge=1, le=1_000)
    summary_max_tokens: int = Field(default=180, ge=16, le=1_000)
    user_agent: str = "weather-joke-summary-service/1.0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Create one settings object for the running process."""
    return Settings()

"""Application settings and configuration."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "SaleWatcher"
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Database
    database_url: str = "postgresql://localhost:5432/salewatcher"

    # Milled.com credentials
    milled_email: str = ""
    milled_password: str = ""

    # Anthropic API
    anthropic_api_key: str = ""

    # Google Calendar
    google_credentials_json: str = ""
    google_calendar_id: str = ""

    # Resend email
    resend_api_key: str = ""
    notification_email: str = ""

    # Dashboard
    dashboard_url: str = "http://localhost:3000"

    # Scraping settings
    scrape_delay_seconds: float = 2.0
    scrape_retry_attempts: int = 3

    # LLM settings
    llm_haiku_model: str = "claude-3-5-haiku-20241022"
    llm_sonnet_model: str = "claude-sonnet-4-20250514"
    llm_confidence_threshold: float = 0.7
    llm_review_threshold: float = 0.5

    # Prediction settings
    prediction_window_days: int = 7
    calendar_alert_days_before: int = 7


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()

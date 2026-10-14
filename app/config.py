"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    """Application settings derived from environment variables.

    All secrets are read exclusively from environment variables.
    No defaults contain real credentials.
    """

    def __init__(self) -> None:
        """Load settings from environment."""
        self.gemini_api_key: str | None = os.environ.get("GEMINI_API_KEY")
        # Default to a current, fast Gemini Flash model.
        self.gemini_model: str = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
        self.app_env: str = os.environ.get("APP_ENV", "development")
        self.cors_origins: list[str] = self._parse_cors_origins(
            os.environ.get("CORS_ORIGINS", "")
        )
        self.rate_limit_rpm: int = int(os.environ.get("RATE_LIMIT_RPM", "20"))
        # Maximum allowed request body size in bytes.
        self.max_body_size: int = 10_240  # 10 KB

    @property
    def is_production(self) -> bool:
        """Return True when running in production mode."""
        return self.app_env.lower() == "production"

    @property
    def docs_enabled(self) -> bool:
        """Expose /docs and /redoc only outside production."""
        return not self.is_production

    @staticmethod
    def _parse_cors_origins(raw: str) -> list[str]:
        """Parse a comma-separated CORS origins string."""
        return [o.strip() for o in raw.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the singleton Settings instance (cached after first call)."""
    return Settings()

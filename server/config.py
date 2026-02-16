"""Server configuration from environment variables."""

from __future__ import annotations

import os


class Settings:
    """Server configuration loaded from environment variables."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://modelab:modelab@localhost:5432/modelab")
    API_KEY: str = os.getenv("MODELAB_API_KEY", "")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8100"))
    CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()

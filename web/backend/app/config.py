"""Backend settings. Reads the shared swarmsense/.env (same one the bridge uses)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

SWARM_ROOT = Path(__file__).resolve().parents[3]
# Make MONGODB_URI / OPENAI_API_KEY etc. available (db_queries also loads this).
load_dotenv(SWARM_ROOT / ".env")


class Settings:
    jwt_secret: str = os.getenv("WEB_JWT_SECRET", "dev-insecure-change-me-nesto-web")
    jwt_algorithm: str = "HS256"
    jwt_expire_seconds: int = int(os.getenv("WEB_JWT_EXPIRE_SECONDS", str(60 * 60 * 12)))  # 12h
    cors_origins: list[str] = [
        o.strip()
        for o in os.getenv("WEB_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
        if o.strip()
    ]


settings = Settings()

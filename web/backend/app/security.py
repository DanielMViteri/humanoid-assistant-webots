"""JWT helpers. Password verification itself is reused from auth_store (PBKDF2)."""
from __future__ import annotations

import time

import jwt

from .config import settings


def create_access_token(claims: dict) -> str:
    now = int(time.time())
    payload = {**claims, "iat": now, "exp": now + settings.jwt_expire_seconds}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])

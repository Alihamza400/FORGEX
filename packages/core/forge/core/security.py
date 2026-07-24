from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel


class TokenData(BaseModel):
    sub: str
    exp: datetime
    scopes: list[str] = []


def generate_api_key() -> str:
    return f"fk_{secrets.token_urlsafe(32)}"


def create_token_data(
    subject: str,
    expire_minutes: int = 1440,
    scopes: list[str] | None = None,
) -> TokenData:
    return TokenData(
        sub=subject,
        exp=datetime.now(UTC) + timedelta(minutes=expire_minutes),
        scopes=scopes or [],
    )


def validate_api_key(key: str) -> bool:
    if not key.startswith("fk_"):
        return False
    return len(key) >= 20

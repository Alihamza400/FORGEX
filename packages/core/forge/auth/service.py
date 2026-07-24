from __future__ import annotations

import hashlib
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from forge.core.config import settings
from forge.core.logging import get_logger
from jose import JWTError, jwt  # type: ignore[import-untyped]

logger = get_logger("forge.auth.service")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.token_expire_minutes
REFRESH_TOKEN_EXPIRE_DAYS = 30


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(
    subject: str,
    roles: list[str] | None = None,
    permissions: list[str] | None = None,
    expire_minutes: int | None = None,
) -> str:
    if not settings.api_secret_key:
        raise ValueError("FORGE_API_SECRET_KEY is not configured")

    expire = expire_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expire)).timestamp()),
        "type": "access",
        "jti": secrets.token_hex(16),
    }
    if roles:
        payload["roles"] = roles
    if permissions:
        payload["permissions"] = permissions

    return jwt.encode(payload, settings.api_secret_key, algorithm=ALGORITHM)  # type: ignore[no-any-return]


def create_refresh_token(subject: str) -> str:
    if not settings.api_secret_key:
        raise ValueError("FORGE_API_SECRET_KEY is not configured")

    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
        "type": "refresh",
        "jti": secrets.token_hex(16),
    }
    return jwt.encode(payload, settings.api_secret_key, algorithm=ALGORITHM)  # type: ignore[no-any-return]


def verify_token(token: str, expected_type: str = "access") -> dict[str, Any]:
    if not settings.api_secret_key:
        raise ValueError("FORGE_API_SECRET_KEY is not configured")

    try:
        payload = jwt.decode(token, settings.api_secret_key, algorithms=[ALGORITHM])
        token_type = payload.get("type")
        if token_type != expected_type:
            raise ValueError(f"Invalid token type: expected {expected_type}, got {token_type}")
        exp = payload.get("exp")
        if exp and time.time() > exp:
            raise ValueError("Token has expired")
        return payload  # type: ignore[no-any-return]
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e


def generate_api_key() -> tuple[str, str, str]:
    raw = f"fk_{secrets.token_urlsafe(32)}"
    prefix = raw[:10]
    hashed = hash_api_key(raw)
    return raw, prefix, hashed


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def verify_api_key(raw_key: str, hashed: str) -> bool:
    return hash_api_key(raw_key) == hashed


def create_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self) -> None:
        self._secret_key = settings.api_secret_key

    def create_access_token(
        self,
        user_id: str,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> str:
        return create_access_token(user_id, roles, permissions)

    def create_refresh_token(self, user_id: str) -> str:
        return create_refresh_token(user_id)

    def verify_access_token(self, token: str) -> dict[str, Any]:
        return verify_token(token, "access")

    def verify_refresh_token(self, token: str) -> dict[str, Any]:
        return verify_token(token, "refresh")

    def hash_password(self, password: str) -> str:
        return hash_password(password)

    def verify_password(self, plain: str, hashed: str) -> bool:
        return verify_password(plain, hashed)

    def generate_api_key(self) -> tuple[str, str, str]:
        return generate_api_key()

    def hash_api_key(self, key: str) -> str:
        return hash_api_key(key)

    def verify_api_key(self, raw_key: str, hashed: str) -> bool:
        return verify_api_key(raw_key, hashed)

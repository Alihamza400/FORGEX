from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from fastapi import FastAPI
from forge.api.main import app as forge_app
from forge.api.routes import auth as auth_routes
from forge.auth.models import UserModel
from forge.auth.service import AuthService
from forge.core.config import settings
from forge.storage.postgres import Database
from httpx import ASGITransport, AsyncClient


@pytest.fixture(autouse=True)
def _patch_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_secret_key", "test-secret-key-1234567890abcdef")
    monkeypatch.setattr(settings, "token_expire_minutes", 1440)
    monkeypatch.setattr(settings, "database_url", "sqlite+aiosqlite://")
    monkeypatch.setattr(settings, "log_level", "CRITICAL")
    monkeypatch.setattr(settings, "metrics_enabled", False)
    monkeypatch.setattr(settings, "tracing_enabled", False)


@pytest_asyncio.fixture
async def test_db() -> AsyncIterator[Database]:
    db = Database(url="sqlite+aiosqlite://")
    await db.connect()
    await db.create_all()
    try:
        yield db
    finally:
        await db.drop_all()
        await db.close()


@pytest_asyncio.fixture
async def auth_service() -> AuthService:
    return AuthService()


@pytest_asyncio.fixture
async def test_user(test_db: Database, auth_service: AuthService) -> dict[str, Any]:
    async with test_db.session() as session:
        user = UserModel(
            username="testuser",
            email="test@example.com",
            password_hash=auth_service.hash_password("TestPass123"),
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
        }


@pytest_asyncio.fixture
async def admin_user(test_db: Database, auth_service: AuthService) -> dict[str, Any]:
    async with test_db.session() as session:
        user = UserModel(
            username="admin",
            email="admin@example.com",
            password_hash=auth_service.hash_password("AdminPass123"),
            is_active=True,
            is_admin=True,
            roles=["admin"],
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
        }


@pytest_asyncio.fixture
async def app(test_db: Database) -> FastAPI:
    async def override_get_db():
        yield test_db

    forge_app.dependency_overrides[auth_routes._get_db] = override_get_db
    try:
        yield forge_app
    finally:
        forge_app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, test_user: dict[str, Any]) -> AsyncClient:
    auth_service = AuthService()
    token = auth_service.create_access_token(
        str(test_user["id"]),
        permissions=["agent:list", "agent:create", "orchestrate:create", "orchestrate:read"],
    )
    client.headers["Authorization"] = f"Bearer {token}"
    return client


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient, admin_user: dict[str, Any]) -> AsyncClient:
    auth_service = AuthService()
    token = auth_service.create_access_token(str(admin_user["id"]), roles=["admin"])
    client.headers["Authorization"] = f"Bearer {token}"
    return client

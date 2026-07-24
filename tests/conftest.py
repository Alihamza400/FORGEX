from __future__ import annotations

from pathlib import Path

import pytest
from forge.core.config import ForgeSettings


@pytest.fixture(autouse=True)
def _patch_auth_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "forge.core.config.settings.api_secret_key",
        "test-secret-key-for-testing-purposes-only-123456",
    )
    monkeypatch.setattr(
        "forge.core.config.settings.token_expire_minutes",
        1440,
    )


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "forge-test"


@pytest.fixture
def test_settings() -> ForgeSettings:
    return ForgeSettings(
        FORGE_LOG_LEVEL="CRITICAL",
        FORGE_API_SECRET_KEY="test-secret-key-for-testing-purposes-only-123456",
        DATABASE_URL="sqlite+aiosqlite:///forge-test.db",
        REDIS_URL="redis://localhost:6379/1",
        QDRANT_URL="http://localhost:6334",
        MINIO_ENDPOINT="localhost:9000",
        OLLAMA_BASE_URL="http://localhost:11435",
    )

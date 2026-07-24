from __future__ import annotations

import subprocess
import time
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient


def _check_docker() -> bool:
    try:
        subprocess.run(
            ["docker", "compose", "ps", "--services"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _wait_for_service(url: str, timeout: int = 60) -> bool:
    import httpx

    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = httpx.get(url, timeout=5)
            if resp.status_code < 500:
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(2)
    return False


@pytest.fixture(scope="session")
def docker_compose_path() -> Path:
    return Path(__file__).parent.parent.parent / "packages" / "deploy" / "docker-compose.yml"


@pytest.fixture(scope="session")
def docker_available() -> bool:
    if not _check_docker():
        pytest.skip("Docker is not available")
    return True


@pytest_asyncio.fixture
async def client(api_url: str) -> AsyncIterator[AsyncClient]:
    ready = _wait_for_service(f"{api_url}/readyz", timeout=120)
    if not ready:
        pytest.skip("API is not available")
    async with AsyncClient(base_url=api_url) as ac:
        yield ac


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    import uuid

    suffix = uuid.uuid4().hex[:8]
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": f"e2e-user-{suffix}",
            "email": f"e2e-{suffix}@example.com",
            "password": "E2eTestPass123",
        },
    )
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def auth_token(client: AsyncClient, registered_user: dict) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"username": registered_user["username"], "password": "E2eTestPass123"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def auth_client(client: AsyncClient, auth_token: str) -> AsyncClient:
    client.headers["Authorization"] = f"Bearer {auth_token}"
    return client

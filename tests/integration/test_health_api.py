from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "0.1.0"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient) -> None:
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Forge API"
    assert data["version"] == "0.1.0"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_readyz_endpoint(client: AsyncClient) -> None:
    response = await client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_livez_endpoint(client: AsyncClient) -> None:
    response = await client.get("/livez")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openapi_schema(client: AsyncClient) -> None:
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Forge API"
    assert "/api/v1/auth/register" in str(schema["paths"])
    assert "/api/v1/auth/login" in str(schema["paths"])
    assert "/api/v1/health" in str(schema["paths"])

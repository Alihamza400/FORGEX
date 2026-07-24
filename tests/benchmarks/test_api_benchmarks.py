from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_health_endpoint_latency(benchmark, client: AsyncClient) -> None:
    async def _get():
        resp = await client.get("/readyz")
        return resp.status_code

    result = benchmark(_get)
    assert result == 200


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_root_endpoint_latency(benchmark, client: AsyncClient) -> None:
    async def _get():
        resp = await client.get("/")
        return resp.status_code

    result = benchmark(_get)
    assert result == 200


@pytest.mark.benchmark
@pytest.mark.asyncio
async def test_openapi_schema_latency(benchmark, client: AsyncClient) -> None:
    async def _get():
        resp = await client.get("/openapi.json")
        return resp.status_code

    result = benchmark(_get)
    assert result == 200

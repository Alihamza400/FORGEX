from __future__ import annotations

import httpx
import pytest_asyncio


@pytest_asyncio.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient(base_url="http://localhost:8000") as ac:
        yield ac

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_agents(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert isinstance(data["agents"], list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_agents_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/agents")
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_agent_valid(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/agents/validate",
        json={
            "config_path": "",
            "config": {
                "name": "test-agent",
                "role": "Test assistant",
                "goal": "Help with testing",
                "model": {"name": "llama3.2:3b", "provider": "ollama"},
                "tools": [{"name": "calculator", "type": "builtin"}],
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is True
    assert data["name"] == "test-agent"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_agent_invalid(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/agents/validate",
        json={"config_path": "/nonexistent/path.yaml", "config": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_validate_agent_unauthorized(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/agents/validate",
        json={
            "config_path": "",
            "config": {
                "name": "test",
                "role": "test",
                "goal": "test",
                "model": {"name": "llama3.2:3b", "provider": "ollama"},
            },
        },
    )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_run_agent_no_config(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/agents/run",
        json={"task": "say hello"},
    )
    assert response.status_code == 400
    assert "config" in response.json()["detail"].lower()

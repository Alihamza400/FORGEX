from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["version"] == "0.1.0"


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient) -> None:
    import uuid

    suffix = uuid.uuid4().hex[:8]
    register_resp = await client.post(
        "/api/v1/auth/register",
        json={
            "username": f"e2e-user-{suffix}",
            "email": f"e2e-{suffix}@example.com",
            "password": "E2eTestPass123",
        },
    )
    assert register_resp.status_code == 201
    user = register_resp.json()
    assert user["username"] == f"e2e-user-{suffix}"

    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": f"e2e-user-{suffix}", "password": "E2eTestPass123"},
    )
    assert login_resp.status_code == 200
    tokens = login_resp.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_full_agent_flow(auth_client: AsyncClient) -> None:
    list_resp = await auth_client.get("/api/v1/agents")
    assert list_resp.status_code == 200

    validate_resp = await auth_client.post(
        "/api/v1/agents/validate",
        json={
            "config_path": "",
            "config": {
                "name": "e2e-test-agent",
                "role": "E2E test assistant",
                "goal": "Answer the user's question concisely",
                "llm_provider": "ollama",
                "llm_model": "llama3.2:3b",
                "tools": ["calculator"],
            },
        },
    )
    assert validate_resp.status_code == 200
    assert validate_resp.json()["valid"] is True


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_api_key_workflow(auth_client: AsyncClient) -> None:
    create_resp = await auth_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "e2e-test-key", "permissions": ["agent:list"], "expires_in_days": 7},
    )
    assert create_resp.status_code == 201
    key_data = create_resp.json()
    assert key_data["name"] == "e2e-test-key"
    assert key_data["key"].startswith("fk_")

    list_resp = await auth_client.get("/api/v1/auth/api-keys")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    revoke_resp = await auth_client.delete(f"/api/v1/auth/api-keys/{key_data['id']}")
    assert revoke_resp.status_code == 200


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_me_endpoint(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert "username" in data
    assert "email" in data
    assert "permissions" in data

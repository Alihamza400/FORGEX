from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "newuser", "email": "new@example.com", "password": "NewUser123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "new@example.com"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "email": "dup1@example.com", "password": "DupUser123"},
    )
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "dup", "email": "dup2@example.com", "password": "DupUser123"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "user1", "email": "same@example.com", "password": "UserOne123"},
    )
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "user2", "email": "same@example.com", "password": "UserTwo123"},
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"username": "weakpw", "email": "weak@example.com", "password": "short"},
    )
    assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_success(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "loginuser", "email": "login@example.com", "password": "LoginUser123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "loginuser", "password": "LoginUser123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "badpw", "email": "badpw@example.com", "password": "BadPwUser123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "badpw", "password": "WrongPassword1"},
    )
    assert response.status_code == 401
    assert "Invalid" in response.json()["detail"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "nobody", "password": "NobodyPass123"},
    )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_token(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/auth/register",
        json={"username": "refreshme", "email": "refresh@example.com", "password": "RefreshMe123"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"username": "refreshme", "password": "RefreshMe123"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_refresh_invalid_token(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid-token-here"},
    )
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_endpoint(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["email"] == "test@example.com"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_me_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.integration
@pytest.mark.asyncio
async def test_change_password(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "TestPass123", "new_password": "NewPass4567"},
    )
    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successfully"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_change_password_wrong_current(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "WrongPass123", "new_password": "NewPass4567"},
    )
    assert response.status_code == 400


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_api_key(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "test-key", "permissions": ["agent:list"], "expires_in_days": 30},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-key"
    assert data["prefix"]
    assert data["key"]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_api_keys(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/api-keys")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoke_api_key(auth_client: AsyncClient) -> None:
    create_resp = await auth_client.post(
        "/api/v1/auth/api-keys",
        json={"name": "revoke-me", "permissions": [], "expires_in_days": 30},
    )
    key_id = create_resp.json()["id"]

    response = await auth_client.delete(f"/api/v1/auth/api-keys/{key_id}")
    assert response.status_code == 200
    assert response.json()["message"] == "API key revoked"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_revoke_nonexistent_key(auth_client: AsyncClient) -> None:
    response = await auth_client.delete("/api/v1/auth/api-keys/99999")
    assert response.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_role(admin_client: AsyncClient) -> None:
    response = await admin_client.post(
        "/api/v1/auth/roles",
        json={"name": "test-role", "description": "A test role", "permissions": ["agent:list"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test-role"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_role_duplicate(admin_client: AsyncClient) -> None:
    await admin_client.post(
        "/api/v1/auth/roles",
        json={"name": "dup-role", "description": "", "permissions": []},
    )
    response = await admin_client.post(
        "/api/v1/auth/roles",
        json={"name": "dup-role", "description": "", "permissions": []},
    )
    assert response.status_code == 409


@pytest.mark.integration
@pytest.mark.asyncio
async def test_create_role_forbidden_for_non_admin(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/auth/roles",
        json={"name": "should-fail", "description": "", "permissions": []},
    )
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_roles(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/api/v1/auth/roles")
    assert response.status_code == 200
    roles = response.json()
    assert isinstance(roles, list)
    assert len(roles) >= 4


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_users(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/api/v1/auth/users")
    assert response.status_code == 200
    users = response.json()
    assert isinstance(users, list)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_users_forbidden(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/auth/users")
    assert response.status_code == 403


@pytest.mark.integration
@pytest.mark.asyncio
async def test_list_audit_logs(admin_client: AsyncClient) -> None:
    response = await admin_client.get("/api/v1/auth/audit-logs")
    assert response.status_code == 200
    logs = response.json()
    assert isinstance(logs, list)

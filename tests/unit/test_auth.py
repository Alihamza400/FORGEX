from __future__ import annotations

import hashlib
from unittest.mock import patch

import pytest
from forge.auth.rbac import (
    ROLE_DEFINITIONS,
    Permission,
    check_permissions,
    get_role_permissions,
    resolve_user_permissions,
    user_has_permission,
)
from forge.auth.schemas import (
    ApiKeyCreateRequest,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenRefreshRequest,
)
from forge.auth.service import (
    AuthService,
    create_access_token,
    create_refresh_token,
    generate_api_key,
    hash_api_key,
    hash_password,
    verify_api_key,
    verify_password,
    verify_token,
)
from pydantic import ValidationError


class TestAuthService:
    def setup_method(self) -> None:
        self.service = AuthService()

    def test_hash_and_verify_password(self):
        hashed = hash_password("TestPass123")
        assert hashed != "TestPass123"
        assert verify_password("TestPass123", hashed) is True
        assert verify_password("WrongPass", hashed) is False

    def test_hash_password_is_bcrypt(self):
        hashed = hash_password("TestPass123")
        assert hashed.startswith("$2b$")

    def test_generate_api_key_format(self):
        raw, prefix, hashed = generate_api_key()
        assert raw.startswith("fk_")
        assert len(raw) > 20
        assert prefix == raw[:10]
        assert len(prefix) == 10

    def test_hash_and_verify_api_key(self):
        raw, _, hashed = generate_api_key()
        assert verify_api_key(raw, hashed) is True
        assert verify_api_key("wrong_key", hashed) is False

    def test_create_and_verify_access_token(self):
        token = self.service.create_access_token(
            "user-1",
            roles=["operator"],
            permissions=["agent:list", "agent:run"],
        )
        payload = self.service.verify_access_token(token)
        assert payload["sub"] == "user-1"
        assert payload["type"] == "access"
        assert "operator" in payload["roles"]
        assert "agent:list" in payload["permissions"]

    def test_create_and_verify_refresh_token(self):
        token = self.service.create_refresh_token("user-1")
        payload = self.service.verify_refresh_token(token)
        assert payload["sub"] == "user-1"
        assert payload["type"] == "refresh"
        assert "jti" in payload

    def test_verify_expired_token_raises(self):
        token = create_access_token("user-1", expire_minutes=-1)
        with pytest.raises(ValueError, match="expired"):
            verify_token(token)

    def test_verify_wrong_type_raises(self):
        token = create_refresh_token("user-1")
        with pytest.raises(ValueError, match="Invalid token type"):
            verify_token(token, "access")

    def test_verify_invalid_token_raises(self):
        with pytest.raises(ValueError, match="Invalid token"):
            verify_token("not.a.token")

    def test_service_uses_secret_key(self):
        with patch("forge.auth.service.settings") as mock_settings:
            mock_settings.api_secret_key = ""
            with pytest.raises(ValueError, match="FORGE_API_SECRET_KEY"):
                self.service.create_access_token("user-1")

    def test_password_hashing_service_methods(self):
        hashed = self.service.hash_password("TestPass123")
        assert self.service.verify_password("TestPass123", hashed) is True
        assert self.service.verify_password("wrong", hashed) is False


class TestAuthSchemas:
    def test_register_request_valid(self):
        req = RegisterRequest(
            username="test-user",
            email="test@example.com",
            password="StrongPass1",
        )
        assert req.username == "test-user"
        assert req.email == "test@example.com"

    def test_register_request_weak_password(self):
        with pytest.raises(ValidationError, match="uppercase"):
            RegisterRequest(
                username="test",
                email="t@t.com",
                password="weakpassword1",
            )

    def test_register_request_no_digit(self):
        with pytest.raises(ValidationError, match="digit"):
            RegisterRequest(
                username="test",
                email="t@t.com",
                password="WeakPassNoDigit",
            )

    def test_register_request_short_username(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="ab",
                email="t@t.com",
                password="StrongPass1",
            )

    def test_login_request_valid(self):
        req = LoginRequest(username="test", password="testpass")
        assert req.username == "test"

    def test_change_password_valid(self):
        req = ChangePasswordRequest(
            current_password="old",
            new_password="NewStrongPass1",
        )
        assert req.new_password == "NewStrongPass1"

    def test_change_password_weak(self):
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                current_password="old",
                new_password="weak",
            )

    def test_api_key_create_request(self):
        req = ApiKeyCreateRequest(name="my-key", expires_in_days=30)
        assert req.name == "my-key"
        assert req.expires_in_days == 30

    def test_api_key_create_request_no_expiry(self):
        req = ApiKeyCreateRequest(name="my-key")
        assert req.expires_in_days is None

    def test_token_refresh_request(self):
        req = TokenRefreshRequest(refresh_token="some.token.here")
        assert req.refresh_token == "some.token.here"

    def test_register_request_invalid_email(self):
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="test",
                email="not-an-email",
                password="StrongPass1",
            )


class TestRBAC:
    def test_role_definitions_exist(self):
        assert "admin" in ROLE_DEFINITIONS
        assert "operator" in ROLE_DEFINITIONS
        assert "developer" in ROLE_DEFINITIONS
        assert "viewer" in ROLE_DEFINITIONS

    def test_admin_has_all_permissions(self):
        admin_perms = set(get_role_permissions("admin"))
        all_perms = {p.value for p in Permission}
        assert admin_perms == all_perms

    def test_get_role_permissions_unknown_role(self):
        perms = get_role_permissions("nonexistent")
        assert perms == []

    def test_user_has_permission_admin_wildcard(self):
        assert user_has_permission(["admin:*"], "agent:list") is True
        assert user_has_permission(["admin:*"], "nonexistent") is True

    def test_user_has_permission_exact(self):
        assert user_has_permission(["agent:list"], "agent:list") is True
        assert user_has_permission(["agent:list"], "agent:run") is False

    def test_check_permissions_all_required(self):
        assert check_permissions(["a", "b", "c"], ["a", "b"]) is True
        assert check_permissions(["a", "b"], ["a", "c"]) is False

    def test_check_permissions_admin_wildcard(self):
        assert check_permissions(["admin:*"], ["a", "b", "c"]) is True

    def test_resolve_user_permissions(self):
        perms = resolve_user_permissions(["operator", "viewer"])
        assert "agent:list" in perms
        assert "agent:run" in perms
        assert "orchestrate:create" in perms
        assert "log:read" in perms

    def test_resolve_user_permissions_empty_roles(self):
        assert resolve_user_permissions([]) == []

    def test_operator_permissions(self):
        perms = set(get_role_permissions("operator"))
        assert "agent:list" in perms
        assert "agent:create" in perms
        assert "orchestrate:create" in perms
        assert "user:list" not in perms  # admin only

    def test_viewer_permissions_are_readonly(self):
        perms = set(get_role_permissions("viewer"))
        assert "agent:list" in perms
        assert "agent:run" not in perms
        assert "orchestrate:create" not in perms

    def test_permission_enum_values(self):
        assert Permission.AGENT_LIST == "agent:list"
        assert Permission.ORCHESTRATE_CREATE == "orchestrate:create"
        assert Permission.ADMIN == "admin:*"


class TestHashUtils:
    def test_hash_api_key_deterministic(self):
        h1 = hash_api_key("test-key-123")
        h2 = hash_api_key("test-key-123")
        assert h1 == h2

    def test_hash_api_key_sha256(self):
        h = hash_api_key("test")
        expected = hashlib.sha256(b"test").hexdigest()
        assert h == expected

    def test_verify_api_key_deterministic(self):
        raw, _, hashed = generate_api_key()
        assert verify_api_key(raw, hashed) is True

    def test_create_token_hash(self):
        from forge.auth.service import create_token_hash

        h1 = create_token_hash("test-token")
        h2 = create_token_hash("test-token")
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex

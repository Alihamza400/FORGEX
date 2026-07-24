from __future__ import annotations

from forge.core.security import create_token_data, generate_api_key, validate_api_key


class TestSecurity:
    def test_generate_api_key_format(self):
        key = generate_api_key()
        assert key.startswith("fk_")
        assert len(key) > 20

    def test_validate_api_key_valid(self):
        key = generate_api_key()
        assert validate_api_key(key) is True

    def test_validate_api_key_invalid_prefix(self):
        assert validate_api_key("invalid_key") is False

    def test_validate_api_key_too_short(self):
        assert validate_api_key("fk_short") is False

    def test_create_token_data(self):
        token = create_token_data("agent-1", expire_minutes=60, scopes=["run"])
        assert token.sub == "agent-1"
        assert "run" in token.scopes
        assert token.exp is not None

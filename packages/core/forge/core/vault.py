from __future__ import annotations

import json
import os
from pathlib import Path

from forge.core.logging import get_logger

logger = get_logger("forge.core.vault")


class VaultError(Exception):
    pass


class SecretsVault:
    def __init__(self, vault_path: str | Path | None = None) -> None:
        self._vault_path = Path(vault_path or "/etc/forge/secrets")
        self._secrets: dict[str, str] = {}
        self._loaded = False

    def load(self) -> None:
        if not self._vault_path.exists():
            logger.info("vault path not found, using env vars", path=str(self._vault_path))
            self._loaded = True
            return

        if self._vault_path.is_dir():
            for f in sorted(self._vault_path.iterdir()):
                if f.is_file() and not f.name.startswith("."):
                    self._secrets[f.name] = f.read_text(encoding="utf-8").strip()
        elif self._vault_path.is_file() and self._vault_path.suffix == ".json":
            raw = self._vault_path.read_text(encoding="utf-8")
            self._secrets = json.loads(raw)
        else:
            raise VaultError(f"Invalid vault path: {self._vault_path}")

        self._loaded = True
        logger.info("loaded secrets from vault",
            path=str(self._vault_path), count=len(self._secrets))

    def get(self, key: str, default: str | None = None) -> str | None:
        if not self._loaded:
            self.load()
        return self._secrets.get(key, default)

    def get_required(self, key: str) -> str:
        value = self.get(key)
        if value is not None:
            return value
        env_val = os.environ.get(key)
        if env_val:
            return env_val
        raise VaultError(f"Required secret not found: {key}")

    def __getitem__(self, key: str) -> str:
        return self.get_required(key)

    def get_all(self) -> dict[str, str]:
        if not self._loaded:
            self.load()
        return dict(self._secrets)

    def set(self, key: str, value: str) -> None:
        self._secrets[key] = value

    def persist(self, path: str | Path | None = None) -> None:
        target = Path(path or self._vault_path)
        if target.suffix == ".json":
            target.write_text(json.dumps(self._secrets, indent=2), encoding="utf-8")
            target.chmod(0o600)
        else:
            target.mkdir(parents=True, exist_ok=True)
            for key, value in self._secrets.items():
                f = target / key
                f.write_text(value, encoding="utf-8")
                f.chmod(0o600)
        logger.info("persisted secrets", path=str(target), count=len(self._secrets))


vault = SecretsVault()


def get_secret(key: str, default: str | None = None) -> str | None:
    return vault.get(key, default)


def get_required_secret(key: str) -> str:
    return vault.get_required(key)

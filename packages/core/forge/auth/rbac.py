from __future__ import annotations

from enum import StrEnum
from typing import Any


class Permission(StrEnum):
    AGENT_LIST = "agent:list"
    AGENT_CREATE = "agent:create"
    AGENT_UPDATE = "agent:update"
    AGENT_DELETE = "agent:delete"
    AGENT_RUN = "agent:run"

    ORCHESTRATE_CREATE = "orchestrate:create"
    ORCHESTRATE_READ = "orchestrate:read"
    ORCHESTRATE_LIST = "orchestrate:list"

    LOG_READ = "log:read"
    LOG_EXPORT = "log:export"

    USER_LIST = "user:list"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"

    ROLE_LIST = "role:list"
    ROLE_CREATE = "role:create"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"

    APIKEY_LIST = "apikey:list"
    APIKEY_CREATE = "apikey:create"
    APIKEY_DELETE = "apikey:delete"

    AUDIT_READ = "audit:read"
    SETTINGS_READ = "settings:read"
    SETTINGS_UPDATE = "settings:update"

    HEALTH_READ = "health:read"
    ADMIN = "admin:*"


ROLE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "admin": {
        "description": "Full system access with all permissions",
        "permissions": [p.value for p in Permission],
        "is_system": True,
    },
    "operator": {
        "description": "Can manage agents, orchestrations, and view logs",
        "permissions": [
            Permission.AGENT_LIST,
            Permission.AGENT_CREATE,
            Permission.AGENT_UPDATE,
            Permission.AGENT_DELETE,
            Permission.AGENT_RUN,
            Permission.ORCHESTRATE_CREATE,
            Permission.ORCHESTRATE_READ,
            Permission.ORCHESTRATE_LIST,
            Permission.LOG_READ,
            Permission.LOG_EXPORT,
            Permission.HEALTH_READ,
        ],
        "is_system": True,
    },
    "developer": {
        "description": "Can run agents and orchestrations, view logs",
        "permissions": [
            Permission.AGENT_LIST,
            Permission.AGENT_RUN,
            Permission.ORCHESTRATE_CREATE,
            Permission.ORCHESTRATE_READ,
            Permission.ORCHESTRATE_LIST,
            Permission.LOG_READ,
            Permission.HEALTH_READ,
            Permission.APIKEY_LIST,
            Permission.APIKEY_CREATE,
        ],
        "is_system": True,
    },
    "viewer": {
        "description": "Read-only access to agents, orchestrations, and logs",
        "permissions": [
            Permission.AGENT_LIST,
            Permission.ORCHESTRATE_READ,
            Permission.ORCHESTRATE_LIST,
            Permission.LOG_READ,
            Permission.HEALTH_READ,
        ],
        "is_system": True,
    },
}


def get_role_permissions(role_name: str) -> list[str]:
    role = ROLE_DEFINITIONS.get(role_name)
    if role is None:
        return []
    return list(role["permissions"])


def user_has_permission(user_permissions: list[str], required: str) -> bool:
    if "admin:*" in user_permissions:
        return True
    return required in user_permissions


def check_permissions(user_permissions: list[str], required: list[str]) -> bool:
    if "admin:*" in user_permissions:
        return True
    return all(p in user_permissions for p in required)


def resolve_user_permissions(roles: list[str]) -> list[str]:
    perms: set[str] = set()
    for role_name in roles:
        perms.update(get_role_permissions(role_name))
    return list(perms)

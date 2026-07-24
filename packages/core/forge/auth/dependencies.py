from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from forge.auth.rbac import check_permissions, resolve_user_permissions
from forge.auth.service import AuthService, verify_api_key
from forge.core.logging import get_logger

logger = get_logger("forge.auth.dependencies")

security_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_auth_service() -> AuthService:
    return AuthService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    api_key: str | None = Depends(api_key_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any]:
    if credentials:
        try:
            payload = auth_service.verify_access_token(credentials.credentials)
            return {
                "id": payload.get("sub", ""),
                "username": payload.get("username", ""),
                "roles": payload.get("roles", []),
                "permissions": payload.get("permissions", []),
                "is_admin": "admin" in payload.get("roles", []),
                "auth_method": "jwt",
            }
        except ValueError as e:
            logger.warning("jwt validation failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e),
                headers={"WWW-Authenticate": "Bearer"},
            ) from e

    if api_key:
        from forge.auth.models import ApiKeyModel
        from forge.storage.postgres import Database

        db = Database()
        await db.connect()
        try:
            async with db.session() as session:
                from sqlalchemy import select

                result = await session.execute(select(ApiKeyModel).where(ApiKeyModel.is_active))
                keys = result.scalars().all()
                for key_model in keys:
                    if verify_api_key(api_key, key_model.hash):
                        key_model.last_used_at = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
                        await session.commit()
                        perms = resolve_user_permissions(key_model.permissions)
                        return {
                            "id": str(key_model.user_id),
                            "username": f"api-key:{key_model.name}",
                            "roles": key_model.permissions,
                            "permissions": perms,
                            "is_admin": "admin" in key_model.permissions,
                            "auth_method": "api_key",
                            "api_key_id": key_model.id,
                        }
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        finally:
            await db.close()

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Provide a Bearer token or X-API-Key header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
    api_key: str | None = Depends(api_key_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, Any] | None:
    try:
        return await get_current_user(credentials, api_key, auth_service)
    except HTTPException:
        return None


def require_permission(*permissions: str):
    async def _check(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not check_permissions(current_user.get("permissions", []), list(permissions)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {', '.join(permissions)}",
            )
        return current_user
    return _check


def require_role(*roles: str):
    async def _check(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        user_roles = current_user.get("roles", [])
        if not any(r in user_roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required one of: {', '.join(roles)}",
            )
        return current_user
    return _check


require_admin = require_role("admin")

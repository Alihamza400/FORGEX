# mypy: ignore-errors
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from forge.auth.dependencies import get_current_user, require_admin
from forge.auth.models import ApiKeyModel, AuditLogModel, RoleModel, SessionModel, UserModel
from forge.auth.rbac import ROLE_DEFINITIONS, resolve_user_permissions
from forge.auth.schemas import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
    AuditLogResponse,
    ChangePasswordRequest,
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    RoleCreateRequest,
    RoleResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserResponse,
)
from forge.auth.service import AuthService, create_token_hash
from forge.storage.postgres import Database
from sqlalchemy import select

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


async def _get_db() -> Database:
    db = Database()
    await db.connect()
    try:
        yield db
    finally:
        await db.close()


async def _audit_log(
    db: Database,
    action: str,
    success: bool,
    user_id: int | None = None,
    username: str | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    request: Request | None = None,
) -> None:
    async with db.session() as session:
        log = AuditLogModel(
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            resource_id=resource_id,
            detail=detail,
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            success=success,
        )
        session.add(log)
        await session.commit()


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(req: RegisterRequest, request: Request, db: Database = Depends(_get_db)):
    async with db.session() as session:
        existing = await session.execute(
            select(UserModel).where(
                (UserModel.username == req.username) | (UserModel.email == req.email),
            ),
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Username or email already exists")

        auth_service = AuthService()
        user = UserModel(
            username=req.username,
            email=req.email,
            password_hash=auth_service.hash_password(req.password),
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        await _audit_log(db, "user.register", True, user.id, user.username,
                          resource="user", resource_id=str(user.id), request=request)

        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_active=user.is_active,
            is_admin=user.is_admin,
            roles=user.roles or [],
            last_login=user.last_login,
            created_at=user.created_at,
        )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request, db: Database = Depends(_get_db)):
    auth_service = AuthService()

    async with db.session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.username == req.username),
        )
        user = result.scalar_one_or_none()

        if not user or not auth_service.verify_password(req.password, user.password_hash):
            await _audit_log(db, "user.login", False, username=req.username,
                              detail="Invalid credentials", request=request)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        if not user.is_active:
            await _audit_log(db, "user.login", False, user.id, user.username,
                              detail="Account disabled", request=request)
            raise HTTPException(status_code=403, detail="Account is disabled")

        perms = resolve_user_permissions(user.roles or [])
        access_token = auth_service.create_access_token(
            str(user.id),
            roles=user.roles or [],
            permissions=perms,
        )
        refresh_token = auth_service.create_refresh_token(str(user.id))

        user.last_login = datetime.now(UTC).replace(tzinfo=None)

        session.add(SessionModel(
            user_id=user.id,
            token_hash=create_token_hash(access_token),
            refresh_token_hash=create_token_hash(refresh_token),
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            expires_at=__import__("datetime").datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None
            ) + __import__("datetime").timedelta(days=30),
        ))
        await session.commit()

        await _audit_log(db, "user.login", True, user.id, user.username,
                          request=request)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: TokenRefreshRequest, request: Request, db: Database = Depends(_get_db)):
    auth_service = AuthService()
    try:
        payload = auth_service.verify_refresh_token(req.refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    user_id = payload.get("sub")
    refresh_hash = create_token_hash(req.refresh_token)

    async with db.session() as session:
        result = await session.execute(
            select(SessionModel).where(
                SessionModel.refresh_token_hash == refresh_hash,
                SessionModel.is_active,
            ),
        )
        session_model = result.scalar_one_or_none()
        if not session_model:
            raise HTTPException(status_code=401, detail="Refresh token has been revoked")

        user_result = await session.execute(
            select(UserModel).where(UserModel.id == int(user_id)),
        )
        user = user_result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or disabled")

        perms = resolve_user_permissions(user.roles or [])
        new_access = auth_service.create_access_token(
            str(user.id),
            roles=user.roles or [],
            permissions=perms,
        )
        new_refresh = auth_service.create_refresh_token(str(user.id))

        session_model.is_active = False
        session.add(SessionModel(
            user_id=user.id,
            token_hash=create_token_hash(new_access),
            refresh_token_hash=create_token_hash(new_refresh),
            ip_address=request.client.host if request else None,
            user_agent=request.headers.get("user-agent") if request else None,
            expires_at=__import__("datetime").datetime.now(UTC).replace(
                hour=0, minute=0, second=0, microsecond=0, tzinfo=None
            ) + __import__("datetime").timedelta(days=30),
        ))
        await session.commit()

        await _audit_log(db, "user.refresh", True, user.id, user.username, request=request)

        return TokenResponse(
            access_token=new_access,
            refresh_token=new_refresh,
        )


@router.post("/change-password", response_model=dict)
async def change_password(
    req: ChangePasswordRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(_get_db),
):
    auth_service = AuthService()

    async with db.session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.id == int(current_user["id"])),
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        if not auth_service.verify_password(req.current_password, user.password_hash):
            await _audit_log(db, "user.change_password", False, user.id, user.username,
                              detail="Incorrect current password", request=request)
            raise HTTPException(status_code=400, detail="Current password is incorrect")

        user.password_hash = auth_service.hash_password(req.new_password)
        await session.commit()

        await _audit_log(db, "user.change_password", True, user.id, user.username,
                          request=request)

        return {"message": "Password changed successfully"}


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(current_user: dict = Depends(get_current_user), db: Database = Depends(_get_db)):
    async with db.session() as session:
        result = await session.execute(
            select(UserModel).where(UserModel.id == int(current_user["id"])),
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        perms = resolve_user_permissions(user.roles or [])
        return CurrentUserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_admin=user.is_admin,
            roles=user.roles or [],
            permissions=perms,
        )


@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=201)
async def create_api_key(
    req: ApiKeyCreateRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(_get_db),
):
    auth_service = AuthService()
    raw_key, prefix, hashed = auth_service.generate_api_key()

    async with db.session() as session:
        api_key = ApiKeyModel(
            prefix=prefix,
            hash=hashed,
            name=req.name,
            user_id=int(current_user["id"]),
            permissions=req.permissions,
            expires_at=(
                datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
                + __import__("datetime").timedelta(days=req.expires_in_days)
            ) if req.expires_in_days else None,
        )
        session.add(api_key)
        await session.commit()
        await session.refresh(api_key)

        await _audit_log(db, "apikey.create", True, int(current_user["id"]),
                          current_user.get("username"), "apikey", str(api_key.id),
                          request=request)

        return ApiKeyCreatedResponse(
            id=api_key.id,
            prefix=api_key.prefix,
            name=api_key.name,
            key=raw_key,
            permissions=api_key.permissions or [],
            is_active=api_key.is_active,
            last_used_at=api_key.last_used_at,
            expires_at=api_key.expires_at,
            created_at=api_key.created_at,
        )


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(_get_db),
):
    async with db.session() as session:
        result = await session.execute(
            select(ApiKeyModel).where(ApiKeyModel.user_id == int(current_user["id"])),
        )
        keys = result.scalars().all()
        return [
            ApiKeyResponse(
                id=k.id,
                prefix=k.prefix,
                name=k.name,
                permissions=k.permissions or [],
                is_active=k.is_active,
                last_used_at=k.last_used_at,
                expires_at=k.expires_at,
                created_at=k.created_at,
            )
            for k in keys
        ]


@router.delete("/api-keys/{key_id}", response_model=dict)
async def revoke_api_key(
    key_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: Database = Depends(_get_db),
):
    async with db.session() as session:
        result = await session.execute(
            select(ApiKeyModel).where(
                ApiKeyModel.id == key_id,
                ApiKeyModel.user_id == int(current_user["id"]),
            ),
        )
        key = result.scalar_one_or_none()
        if not key:
            raise HTTPException(status_code=404, detail="API key not found")

        key.is_active = False
        await session.commit()

        await _audit_log(db, "apikey.revoke", True, int(current_user["id"]),
                          current_user.get("username"), "apikey", str(key_id),
                          request=request)

        return {"message": "API key revoked"}


@router.post("/roles", response_model=RoleResponse, status_code=201)
async def create_role(
    req: RoleCreateRequest,
    request: Request,
    db: Database = Depends(_get_db),
    _: dict = Depends(require_admin),
):
    async with db.session() as session:
        existing = await session.execute(
            select(RoleModel).where(RoleModel.name == req.name),
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Role already exists")

        role = RoleModel(
            name=req.name,
            description=req.description,
            permissions=req.permissions,
        )
        session.add(role)
        await session.commit()
        await session.refresh(role)

        await _audit_log(db, "role.create", True, resource="role", resource_id=str(role.id),
                          detail=f"Created role {role.name}", request=request)

        return RoleResponse(
            id=role.id,
            name=role.name,
            description=role.description or "",
            permissions=role.permissions or [],
            is_system=role.is_system,
            created_at=role.created_at,
        )


@router.get("/roles", response_model=list[RoleResponse])
async def list_roles(
    db: Database = Depends(_get_db),
    _: dict = Depends(require_admin),
):
    async with db.session() as session:
        result = await session.execute(select(RoleModel))
        roles = result.scalars().all()
        system_roles = [
            RoleResponse(
                id=0,
                name=name,
                description=defn["description"],
                permissions=list(defn["permissions"]),
                is_system=True,
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            for name, defn in ROLE_DEFINITIONS.items()
        ]
        db_roles = [
            RoleResponse(
                id=r.id,
                name=r.name,
                description=r.description or "",
                permissions=r.permissions or [],
                is_system=r.is_system,
                created_at=r.created_at,
            )
            for r in roles
        ]
        return system_roles + db_roles


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: Database = Depends(_get_db),
    _: dict = Depends(require_admin),
):
    async with db.session() as session:
        result = await session.execute(select(UserModel).order_by(UserModel.created_at.desc()))
        users = result.scalars().all()
        return [
            UserResponse(
                id=u.id,
                username=u.username,
                email=u.email,
                is_active=u.is_active,
                is_admin=u.is_admin,
                roles=u.roles or [],
                last_login=u.last_login,
                created_at=u.created_at,
            )
            for u in users
        ]


@router.get("/audit-logs", response_model=list[AuditLogResponse])
async def list_audit_logs(
    page: int = 1,
    page_size: int = 50,
    db: Database = Depends(_get_db),
    _: dict = Depends(require_admin),
):
    async with db.session() as session:
        offset = (page - 1) * page_size
        result = await session.execute(
            select(AuditLogModel)
            .order_by(AuditLogModel.timestamp.desc())
            .limit(page_size)
            .offset(offset),
        )
        logs = result.scalars().all()
        return [
            AuditLogResponse(
                id=log.id,
                user_id=log.user_id,
                username=log.username,
                action=log.action,
                resource=log.resource,
                resource_id=log.resource_id,
                detail=log.detail,
                ip_address=log.ip_address,
                success=log.success,
                timestamp=log.timestamp,
            )
            for log in logs
        ]

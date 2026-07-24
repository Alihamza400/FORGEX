from __future__ import annotations

from datetime import UTC, datetime

from forge.storage.postgres import Base
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission", String(128), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class UserModel(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    roles = Column(JSON, default=list, nullable=False)

    def __repr__(self) -> str:
        return f"<UserModel(id={self.id}, username='{self.username}')>"


class RoleModel(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(64), unique=True, nullable=False, index=True)
    description = Column(String(512), nullable=True)
    permissions = Column(JSON, default=list, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<RoleModel(id={self.id}, name='{self.name}')>"


class ApiKeyModel(Base):
    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prefix = Column(String(8), nullable=False, index=True)
    hash = Column(String(255), nullable=False)
    name = Column(String(128), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    permissions = Column(JSON, default=list, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ApiKeyModel(id={self.id}, prefix='{self.prefix}', name='{self.name}')>"


class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token_hash = Column(String(255), unique=True, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=_utcnow, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<SessionModel(id={self.id}, user_id={self.user_id})>"


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    username = Column(String(64), nullable=True)
    action = Column(String(128), nullable=False, index=True)
    resource = Column(String(256), nullable=True)
    resource_id = Column(String(64), nullable=True)
    detail = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(512), nullable=True)
    success = Column(Boolean, nullable=False)
    timestamp = Column(DateTime, default=_utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<AuditLogModel(id={self.id}, action='{self.action}', success={self.success})>"

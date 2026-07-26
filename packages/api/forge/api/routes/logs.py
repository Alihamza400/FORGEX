from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from forge.auth.dependencies import require_permission
from forge.storage.postgres import Database
from forge.storage.repository import LogRepository
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/logs", tags=["logs"])


class LogEntry(BaseModel):
    id: int
    agent_name: str
    level: str
    message: str
    timestamp: str


async def get_db() -> Database:
    db = Database()
    await db.connect()
    return db


@router.get("", response_model=list[LogEntry])
async def list_logs(
    agent_name: str | None = Query(None, description="Filter by agent name"),
    level: str | None = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: Any = Depends(require_permission("logs:read")),
) -> list[LogEntry]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = LogRepository(session)
            if agent_name:
                logs = await repo.list_by_agent(agent_name, limit=limit, offset=offset, level=level)
            else:
                logs = []
            return [
                LogEntry(
                    id=log.id,
                    agent_name=log.agent_name,
                    level=log.level,
                    message=log.message[:500],
                    timestamp=str(log.timestamp),
                )
                for log in logs
            ]
    finally:
        await db.close()


@router.get("/{agent_name}", response_model=list[LogEntry])
async def get_agent_logs(
    agent_name: str,
    level: str | None = Query(None, description="Filter by log level"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _: Any = Depends(require_permission("logs:read")),
) -> list[LogEntry]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = LogRepository(session)
            logs = await repo.list_by_agent(agent_name, limit=limit, offset=offset, level=level)
            return [
                LogEntry(
                    id=log.id,
                    agent_name=log.agent_name,
                    level=log.level,
                    message=log.message[:500],
                    timestamp=str(log.timestamp),
                )
                for log in logs
            ]
    finally:
        await db.close()

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from forge.auth.dependencies import require_permission
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/filesystem", tags=["filesystem"])

_workspace_dir: str = ""


class BrowseEntry(BaseModel):
    name: str
    path: str
    type: str
    size: int
    modified: float


class BrowseResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[BrowseEntry]


class WorkspaceResponse(BaseModel):
    workspace: str


class WorkspaceUpdateRequest(BaseModel):
    workspace: str


@router.get("/browse", response_model=BrowseResponse)
async def browse(
    path: str = Query(default="", description="Directory path to browse"),
    _: Any = Depends(require_permission("settings:read")),
) -> BrowseResponse:
    try:
        if not path:
            path = str(Path.home())

        p = Path(path).resolve()
        if not p.exists():
            raise HTTPException(status_code=404, detail="Path does not exist")
        if not p.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

        entries: list[BrowseEntry] = []
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            try:
                stat = entry.stat()
                entries.append(
                    BrowseEntry(
                        name=entry.name,
                        path=str(entry.resolve()),
                        type="directory" if entry.is_dir() else "file",
                        size=stat.st_size,
                        modified=stat.st_mtime,
                    )
                )
            except PermissionError:
                continue

        parent = str(p.parent) if p.parent != p else None

        return BrowseResponse(
            path=str(p),
            parent=parent,
            entries=entries[:200],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workspace", response_model=WorkspaceResponse)
async def get_workspace(
    _: Any = Depends(require_permission("settings:read")),
) -> WorkspaceResponse:
    return WorkspaceResponse(workspace=_workspace_dir)


@router.post("/workspace", response_model=WorkspaceResponse)
async def set_workspace(
    req: WorkspaceUpdateRequest,
    _: Any = Depends(require_permission("settings:update")),
) -> WorkspaceResponse:
    global _workspace_dir

    if req.workspace:
        p = Path(req.workspace).resolve()
        if not p.exists():
            raise HTTPException(status_code=404, detail="Directory does not exist")
        if not p.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")

    _workspace_dir = req.workspace
    return WorkspaceResponse(workspace=_workspace_dir)

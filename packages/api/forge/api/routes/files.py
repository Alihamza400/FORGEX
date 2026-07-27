from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from forge.auth.dependencies import require_permission
from forge.storage.minio import MinIOStorage
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/files", tags=["files"])


class FileInfo(BaseModel):
    key: str
    size: int
    etag: str
    last_modified: str


class FileListResponse(BaseModel):
    files: list[FileInfo]


def get_storage() -> MinIOStorage:
    return MinIOStorage()


@router.get("", response_model=FileListResponse)
async def list_files(
    prefix: str = "",
    _: Any = Depends(require_permission("settings:read")),
) -> FileListResponse:
    storage = get_storage()
    try:
        raw = await storage.list_files(prefix=prefix)
        return FileListResponse(
            files=[
                FileInfo(
                    key=f["key"],
                    size=f["size"],
                    etag=f["etag"],
                    last_modified=f["last_modified"],
                )
                for f in raw
            ],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(
    file: UploadFile,
    _: Any = Depends(require_permission("settings:update")),
) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    storage = get_storage()
    try:
        data = await file.read()
        result = await storage.upload_bytes(
            data=data,
            key=file.filename,
            content_type=file.content_type or "application/octet-stream",
        )
        return {"status": "ok", "key": file.filename, "path": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{key:path}")
async def download_file(
    key: str,
    _: Any = Depends(require_permission("settings:read")),
) -> Response:
    storage = get_storage()
    try:
        data = await storage.download_bytes(key=key)
        return Response(
            content=data,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{key.split("/")[-1]}"',
            },
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{key:path}")
async def delete_file(
    key: str,
    _: Any = Depends(require_permission("settings:update")),
) -> dict[str, Any]:
    storage = get_storage()
    try:
        await storage.delete_file(key=key)
        return {"status": "ok", "key": key}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

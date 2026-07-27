from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from forge.auth.dependencies import require_permission
from forge.core.logging import get_logger
from forge.storage.postgres import Database
from forge.storage.repository import McpServerRepository
from forge.tools.mcp_client import MCPClient, MCPConnectionError
from forge.tools.registry import ToolRegistry
from pydantic import BaseModel

logger = get_logger("forge.api.routes.mcp_servers")

router = APIRouter(prefix="/api/v1/mcp/servers", tags=["mcp"])


class McpServerResponse(BaseModel):
    id: int
    name: str
    transport_type: str
    url: str | None
    command: str | None
    cwd: str | None
    status: str
    config: dict[str, Any] | None
    created_at: str
    updated_at: str


class CreateMcpServerRequest(BaseModel):
    name: str
    transport_type: str = "http"
    url: str | None = None
    command: str | None = None
    cwd: str | None = None
    config: dict[str, Any] | None = None


class McpServerTestResult(BaseModel):
    connected: bool
    tools: list[dict[str, Any]] = []
    error: str | None = None


class McpServerConnectResult(BaseModel):
    connected: bool
    tools_registered: int
    error: str | None = None


async def get_db() -> Database:
    db = Database()
    await db.connect()
    return db


def _model_to_response(server: Any) -> McpServerResponse:
    return McpServerResponse(
        id=server.id,
        name=server.name,
        transport_type=server.transport_type,
        url=server.url,
        command=server.command,
        cwd=server.cwd,
        status=server.status,
        config=server.config,
        created_at=str(server.created_at),
        updated_at=str(server.updated_at),
    )


async def _create_client(server: Any) -> MCPClient:
    if server.transport_type == "stdio":
        if not server.command:
            raise HTTPException(status_code=400, detail="command is required for stdio transport")
        import shlex
        return MCPClient.create_stdio(
            command=shlex.split(server.command),
            cwd=server.cwd,
        )
    if not server.url:
        raise HTTPException(status_code=400, detail="url is required for http transport")
    return MCPClient.create_http(url=server.url)


@router.get("", response_model=list[McpServerResponse])
async def list_mcp_servers(
    _: Any = Depends(require_permission("settings:read")),
) -> list[McpServerResponse]:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = McpServerRepository(session)
            servers = await repo.list_all()
            return [_model_to_response(s) for s in servers]
    finally:
        await db.close()


@router.post("", response_model=McpServerResponse, status_code=201)
async def create_mcp_server(
    req: CreateMcpServerRequest,
    _: Any = Depends(require_permission("settings:update")),
) -> McpServerResponse:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = McpServerRepository(session)
            existing = await repo.get_by_name(req.name)
            if existing:
                raise HTTPException(status_code=409, detail=f"MCP server '{req.name}' already exists")
            server = await repo.create(
                name=req.name,
                transport_type=req.transport_type,
                url=req.url,
                command=req.command,
                cwd=req.cwd,
                config=req.config,
            )
            return _model_to_response(server)
    finally:
        await db.close()


@router.delete("/{server_id}", response_model=dict[str, Any])
async def delete_mcp_server(
    server_id: int,
    _: Any = Depends(require_permission("settings:update")),
) -> dict[str, Any]:
    registry = ToolRegistry.get_instance()
    db = await get_db()
    try:
        async with db.session() as session:
            repo = McpServerRepository(session)
            server = await repo.get_by_id(server_id)
            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")
            registry.unregister(f"mcp:{server.name}")
            await repo.delete(server_id)
            return {"status": "ok", "name": server.name}
    finally:
        await db.close()


@router.post("/{server_id}/test", response_model=McpServerTestResult)
async def test_mcp_server(
    server_id: int,
    _: Any = Depends(require_permission("settings:read")),
) -> McpServerTestResult:
    db = await get_db()
    try:
        async with db.session() as session:
            repo = McpServerRepository(session)
            server = await repo.get_by_id(server_id)
            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            client = await _create_client(server)
            try:
                await client.connect()
                tools = [{"name": t.name, "description": t.description} for t in (await client.list_tools())]
                await client.close()
                return McpServerTestResult(connected=True, tools=tools)
            except MCPConnectionError as e:
                return McpServerTestResult(connected=False, error=str(e))
            except Exception as e:
                return McpServerTestResult(connected=False, error=str(e))
    finally:
        await db.close()


@router.post("/{server_id}/connect", response_model=McpServerConnectResult)
async def connect_mcp_server(
    server_id: int,
    _: Any = Depends(require_permission("settings:update")),
) -> McpServerConnectResult:
    registry = ToolRegistry.get_instance()
    db = await get_db()
    try:
        async with db.session() as session:
            repo = McpServerRepository(session)
            server = await repo.get_by_id(server_id)
            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")

            client = await _create_client(server)
            try:
                await client.connect()
                tools = await client.list_tools()
                registry.unregister(f"mcp:{server.name}")
                for spec in tools:
                    registry.register(
                        name=f"mcp:{server.name}:{spec.name}",
                        mcp_client=client,
                        description=spec.description,
                    )
                await repo.update_status(server_id, "connected")
                return McpServerConnectResult(connected=True, tools_registered=len(tools))
            except MCPConnectionError as e:
                await repo.update_status(server_id, "error")
                return McpServerConnectResult(connected=False, error=str(e))
            except Exception as e:
                await repo.update_status(server_id, "error")
                return McpServerConnectResult(connected=False, error=str(e))
    finally:
        await db.close()


@router.post("/{server_id}/disconnect", response_model=dict[str, Any])
async def disconnect_mcp_server(
    server_id: int,
    _: Any = Depends(require_permission("settings:update")),
) -> dict[str, Any]:
    registry = ToolRegistry.get_instance()
    db = await get_db()
    try:
        async with db.session() as session:
            repo = McpServerRepository(session)
            server = await repo.get_by_id(server_id)
            if not server:
                raise HTTPException(status_code=404, detail="MCP server not found")
            prefix = f"mcp:{server.name}:"
            for tool_name in registry.list_tools():
                if tool_name.startswith(prefix):
                    registry.unregister(tool_name)
            await repo.update_status(server_id, "disconnected")
            return {"status": "ok", "name": server.name}
    finally:
        await db.close()

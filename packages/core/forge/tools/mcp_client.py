from __future__ import annotations

from typing import Any

from forge.core.logging import get_logger
from forge.tools.mcp_protocol import (
    MCPToolSpec,
    build_call_tool_request,
    build_initialize_request,
    build_list_tools_request,
    is_notification,
    parse_initialize_result,
    parse_response,
    parse_tool_call_result,
    parse_tool_list,
)
from forge.tools.mcp_transport import (
    HTTPTransport,
    MCPTransport,
    StdioTransport,
)

logger = get_logger("forge.tools.mcp_client")

REQUEST_TIMEOUT_SECONDS = 60


class MCPError(Exception):
    pass


class MCPConnectionError(MCPError):
    pass


class MCPToolCallError(MCPError):
    pass


class MCPClient:
    def __init__(self, transport: MCPTransport) -> None:
        self.transport = transport
        self._initialized = False
        self._tools: list[MCPToolSpec] = []
        self._next_id = 100

    @classmethod
    def create_stdio(cls, command: list[str], cwd: str | None = None) -> MCPClient:
        return cls(StdioTransport(command=command, cwd=cwd))

    @classmethod
    def create_http(cls, url: str) -> MCPClient:
        return cls(HTTPTransport(url=url))

    async def connect(self) -> None:
        logger.info("connecting to mcp server")
        await self.transport.connect()
        await self._initialize()
        self._tools = await self._discover_tools()
        self._initialized = True
        logger.info("mcp server initialized", tools=len(self._tools))

    async def _initialize(self) -> None:
        req = build_initialize_request()
        req.id = self._next_id
        self._next_id += 1
        await self.transport.send(req.to_dict())
        response = await self._wait_for_response(req.id)

        if response.error:
            raise MCPConnectionError(
                f"Initialize failed: {response.error.get('message', 'unknown')}",
            )
        init_result = parse_initialize_result({"result": response.result})
        logger.info(
            "mcp initialized",
            protocol=init_result.protocol_version,
            server=init_result.server_info,
        )

    async def _discover_tools(self) -> list[MCPToolSpec]:
        req = build_list_tools_request(request_id=self._next_id)
        self._next_id += 1
        await self.transport.send(req.to_dict())
        response = await self._wait_for_response(req.id)

        if response.error:
            logger.warning(
                "failed to list tools",
                error=response.error.get("message", ""),
            )
            return []
        return parse_tool_list({"result": response.result})

    async def list_tools(self) -> list[MCPToolSpec]:
        if not self._initialized:
            await self.connect()
        return self._tools

    async def call_tool(self, name: str, args: dict[str, Any]) -> str:
        if not self._initialized:
            await self.connect()

        tool_ids = {t.name for t in self._tools}
        if tool_ids and name not in tool_ids:
            available = ", ".join(sorted(tool_ids))
            raise MCPToolCallError(
                f"Tool '{name}' not found. Available: {available}",
            )

        req = build_call_tool_request(name, args, request_id=self._next_id)
        self._next_id += 1

        logger.info("calling mcp tool", tool=name, args=args)
        await self.transport.send(req.to_dict())
        response = await self._wait_for_response(req.id)

        if response.error:
            msg = response.error.get("message", "unknown")
            raise MCPToolCallError(f"Tool '{name}' failed: {msg}")

            result_text = parse_tool_call_result({"result": response.result})
        logger.info("mcp tool returned", tool=name, result_len=len(result_text))
        return result_text

    async def _wait_for_response(self, expected_id: int | str | None) -> Any:
        import asyncio

        deadline = asyncio.get_running_loop().time() + REQUEST_TIMEOUT_SECONDS

        while asyncio.get_running_loop().time() < deadline:
            msg = await self.transport.receive()
            if msg is None:
                raise MCPConnectionError("Connection closed by server")

            if is_notification(msg):
                logger.debug("received mcp notification", method=msg.get("method"))
                continue

            response = parse_response(msg)
            if response.id == expected_id:
                return response
            logger.debug(
                "received response for different id",
                expected=expected_id,
                got=response.id,
            )
        else:
            raise MCPError(f"Timeout waiting for response (id={expected_id})")

    async def close(self) -> None:
        await self.transport.close()
        self._initialized = False
        logger.info("mcp client closed")

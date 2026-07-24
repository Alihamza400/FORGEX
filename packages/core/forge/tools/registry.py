from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from forge.core.logging import get_logger
from forge.tools.mcp_client import MCPClient, MCPToolCallError

logger = get_logger("forge.tools.registry")

ToolHandler = Callable[..., Any]


@dataclass
class ToolEntry:
    name: str
    handler: ToolHandler | None = None
    mcp_client: MCPClient | None = None
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolNotFoundError(Exception):
    pass


class ToolExecutionError(Exception):
    pass


class ToolRegistry:
    _instance: ToolRegistry | None = None

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}

    @classmethod
    def get_instance(cls) -> ToolRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def register(
        self,
        name: str,
        handler: ToolHandler | None = None,
        mcp_client: MCPClient | None = None,
        description: str = "",
    ) -> None:
        if name in self._tools:
            logger.warning("overwriting existing tool", name=name)
        self._tools[name] = ToolEntry(
            name=name,
            handler=handler,
            mcp_client=mcp_client,
            description=description,
        )
        tool_type = "mcp" if mcp_client else "builtin"
        logger.info("registered tool", name=name, type=tool_type)

    def register_mcp_client(self, client: MCPClient, prefix: str = "") -> None:
        import asyncio

        if not client._initialized:
            asyncio.get_event_loop().run_until_complete(client.connect())

        for spec in client._tools:
            full_name = f"{prefix}{spec.name}" if prefix else spec.name
            self._tools[full_name] = ToolEntry(
                name=full_name,
                mcp_client=client,
                description=spec.description,
            )
            logger.info("registered mcp tool", name=full_name)

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)
        logger.info("unregistered tool", name=name)

    def get_entry(self, name: str) -> ToolEntry:
        entry = self._tools.get(name)
        if entry is None:
            raise ToolNotFoundError(
                f"Tool '{name}' not found. Available: {', '.join(self.list_tools())}",
            )
        return entry

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def list_entries(self) -> list[ToolEntry]:
        return list(self._tools.values())

    async def execute(self, name: str, args: dict[str, Any]) -> Any:
        entry = self.get_entry(name)

        try:
            if entry.mcp_client is not None:
                return await entry.mcp_client.call_tool(name, args)

            if entry.handler is not None:
                result = entry.handler(**args)
                if hasattr(result, "__await__"):
                    result = await result
                return result

            raise ToolExecutionError(f"Tool '{name}' has no handler or mcp client")

        except ToolNotFoundError:
            raise
        except MCPToolCallError:
            raise
        except Exception as e:
            raise ToolExecutionError(f"Tool '{name}' failed: {e}") from e

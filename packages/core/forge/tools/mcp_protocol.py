from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

JSON = dict[str, Any] | list[Any] | str | int | float | bool | None


@dataclass
class JSONRPCRequest:
    jsonrpc: str = "2.0"
    method: str = ""
    params: dict[str, Any] | None = None
    id: int | str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "id": self.id,
        }
        if self.params is not None:
            d["params"] = self.params
        return d


@dataclass
class JSONRPCResponse:
    jsonrpc: str = "2.0"
    result: JSON | None = None
    error: dict[str, Any] | None = None
    id: int | str | None = None


@dataclass
class MCPToolSpec:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}},
    )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPToolSpec:
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", data.get("input_schema", {})),
        )


@dataclass
class MCPInitializeResult:
    protocol_version: str
    capabilities: dict[str, Any]
    server_info: dict[str, Any]


def build_initialize_request() -> JSONRPCRequest:
    return JSONRPCRequest(
        method="initialize",
        params={
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {
                "name": "forge",
                "version": "0.1.0",
            },
        },
        id=1,
    )


def build_list_tools_request(request_id: int = 2) -> JSONRPCRequest:
    return JSONRPCRequest(method="tools/list", id=request_id)


def build_call_tool_request(
    name: str,
    args: dict[str, Any],
    request_id: int = 3,
) -> JSONRPCRequest:
    return JSONRPCRequest(
        method="tools/call",
        params={"name": name, "arguments": args},
        id=request_id,
    )


def parse_response(data: dict[str, Any]) -> JSONRPCResponse:
    return JSONRPCResponse(
        jsonrpc=data.get("jsonrpc", "2.0"),
        result=data.get("result"),
        error=data.get("error"),
        id=data.get("id"),
    )


def is_notification(data: dict[str, Any]) -> bool:
    return "method" in data and "id" not in data


def parse_initialize_result(data: dict[str, Any]) -> MCPInitializeResult:
    result = data.get("result", {})
    return MCPInitializeResult(
        protocol_version=result.get("protocolVersion", ""),
        capabilities=result.get("capabilities", {}),
        server_info=result.get("serverInfo", {}),
    )


def parse_tool_list(data: dict[str, Any]) -> list[MCPToolSpec]:
    result = data.get("result", {})
    tools = result.get("tools", [])
    return [MCPToolSpec.from_dict(t) for t in tools]


def parse_tool_call_result(data: dict[str, Any]) -> Any:
    result = data.get("result", {})
    content = result.get("content", [])
    if isinstance(content, list):
        texts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    texts.append(item.get("text", ""))
                elif item.get("type") == "resource":
                    texts.append(str(item.get("resource", "")))
            else:
                texts.append(str(item))
        return "\n".join(texts)
    return str(content)

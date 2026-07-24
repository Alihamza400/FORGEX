from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

try:
    import orjson

    def _dumps(data: Any) -> str:
        return orjson.dumps(data).decode("utf-8")

    def _loads(data: str) -> Any:
        return orjson.loads(data)
except ImportError:
    import json

    def _dumps(data: Any) -> str:
        return json.dumps(data)

    def _loads(data: str) -> Any:
        return json.loads(data)


ALLOWED_BASE = Path("/data").resolve()
TOOLS = [
    {
        "name": "read_file",
        "description": "Read the contents of a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "search_files",
        "description": "Search for files matching a glob pattern",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern"},
                "path": {"type": "string", "description": "Directory to search"},
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "file_info",
        "description": "Get information about a file or directory",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
            },
            "required": ["path"],
        },
    },
]


def _resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    if not path.is_absolute():
        path = ALLOWED_BASE / path
    path = path.resolve()
    if not str(path).startswith(str(ALLOWED_BASE)):
        raise PermissionError(f"Access denied: {path}")
    return path


def _handle_read_file(args: dict[str, Any]) -> str:
    path = _resolve_path(args["path"])
    if not path.is_file():
        raise FileNotFoundError(f"Not a file: {path}")
    return path.read_text(encoding="utf-8")


def _handle_write_file(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(args["content"], encoding="utf-8")
    return {"written": str(path), "size": len(args["content"])}


def _handle_list_directory(args: dict[str, Any]) -> list[dict[str, Any]]:
    path = _resolve_path(args.get("path", ""))
    if not path.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")
    entries = []
    for entry in sorted(path.iterdir()):
        entries.append({
            "name": entry.name,
            "type": "directory" if entry.is_dir() else "file",
            "size": entry.stat().st_size if entry.is_file() else 0,
        })
    return entries


def _handle_search_files(args: dict[str, Any]) -> list[dict[str, Any]]:
    base = _resolve_path(args.get("path", ""))
    pattern = args["pattern"]
    matches = list(base.rglob(pattern))
    results = []
    for m in sorted(matches)[:100]:
        results.append({
            "path": str(m),
            "type": "directory" if m.is_dir() else "file",
            "size": m.stat().st_size if m.is_file() else 0,
        })
    return results


def _handle_file_info(args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(args["path"])
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    stat = path.stat()
    return {
        "path": str(path),
        "type": "directory" if path.is_dir() else "file",
        "size": stat.st_size,
        "modified": stat.st_mtime,
        "created": stat.st_ctime,
    }


HANDLERS = {
    "read_file": _handle_read_file,
    "write_file": _handle_write_file,
    "list_directory": _handle_list_directory,
    "search_files": _handle_search_files,
    "file_info": _handle_file_info,
}


def _send_message(msg: dict[str, Any]) -> None:
    line = _dumps(msg)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _read_message() -> dict[str, Any] | None:
    line = sys.stdin.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return None
    return _loads(line)  # type: ignore[no-any-return]


def _handle_request(msg: dict[str, Any]) -> dict[str, Any]:
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2025-03-26",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "forge-mcp-filesystem", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        handler = HANDLERS.get(tool_name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Tool not found: {tool_name}"},
            }
        try:
            result = handler(arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                _dumps(result)
                                if isinstance(result, (dict, list))
                                else str(result)
                            ),
                        },
                    ],
                },
            }
        except (PermissionError, FileNotFoundError, NotADirectoryError) as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32000, "message": str(e)},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": f"Internal error: {e}"},
            }

    if method == "shutdown":
        return {"jsonrpc": "2.0", "id": msg_id, "result": None}

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    while True:
        msg = _read_message()
        if msg is None:
            break
        response = _handle_request(msg)
        _send_message(response)


if __name__ == "__main__":
    main()

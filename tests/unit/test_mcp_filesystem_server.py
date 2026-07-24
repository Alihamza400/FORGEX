from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SERVER_PATH = str(
    Path(__file__).resolve().parent.parent.parent
    / "packages/server-mcp/filesystem/forge_mcp_filesystem/server.py",
)


def _send_and_receive(proc: subprocess.Popen, msg: dict) -> dict:
    line = json.dumps(msg) + "\n"
    proc.stdin.write(line.encode("utf-8"))
    proc.stdin.flush()
    response = proc.stdout.readline()
    return json.loads(response.decode("utf-8"))


@pytest.fixture
def mcp_server():
    proc = subprocess.Popen(
        [sys.executable, SERVER_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    yield proc
    proc.terminate()
    proc.wait()


def test_initialize(mcp_server):
    response = _send_and_receive(mcp_server, {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {}},
        "id": 1,
    })
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    result = response["result"]
    assert result["protocolVersion"] == "2025-03-26"
    assert result["serverInfo"]["name"] == "forge-mcp-filesystem"


def test_list_tools(mcp_server):
    _send_and_receive(mcp_server, {
        "jsonrpc": "2.0", "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {}},
        "id": 1,
    })

    response = _send_and_receive(mcp_server, {
        "jsonrpc": "2.0", "method": "tools/list", "id": 2,
    })
    assert response["jsonrpc"] == "2.0"
    tools = response["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "list_directory" in tool_names
    assert "search_files" in tool_names
    assert "file_info" in tool_names


def test_call_tool_method_not_found(mcp_server):
    _send_and_receive(mcp_server, {
        "jsonrpc": "2.0", "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {}},
        "id": 1,
    })

    response = _send_and_receive(mcp_server, {
        "jsonrpc": "2.0", "method": "tools/call",
        "params": {"name": "nonexistent", "arguments": {}},
        "id": 3,
    })
    assert response["error"]["code"] == -32601


def test_shutdown(mcp_server):
    _send_and_receive(mcp_server, {
        "jsonrpc": "2.0", "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {}},
        "id": 1,
    })

    response = _send_and_receive(mcp_server, {
        "jsonrpc": "2.0", "method": "shutdown", "id": 4,
    })
    assert response["result"] is None

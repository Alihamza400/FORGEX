from __future__ import annotations

from forge.tools.mcp_protocol import (
    MCPToolSpec,
    build_call_tool_request,
    build_initialize_request,
    build_list_tools_request,
    parse_response,
    parse_tool_call_result,
    parse_tool_list,
)


def test_build_initialize_request():
    req = build_initialize_request()
    assert req.method == "initialize"
    assert req.jsonrpc == "2.0"
    assert req.id == 1
    assert req.params is not None
    assert req.params["protocolVersion"] == "2025-03-26"
    assert req.params["clientInfo"]["name"] == "forge"


def test_build_list_tools_request():
    req = build_list_tools_request(request_id=42)
    assert req.method == "tools/list"
    assert req.id == 42


def test_build_call_tool_request():
    req = build_call_tool_request("read_file", {"path": "/test.txt"}, request_id=7)
    assert req.method == "tools/call"
    assert req.params["name"] == "read_file"
    assert req.params["arguments"]["path"] == "/test.txt"
    assert req.id == 7


def test_parse_response_success():
    raw = {"jsonrpc": "2.0", "result": {"tools": []}, "id": 1}
    resp = parse_response(raw)
    assert resp.result == {"tools": []}
    assert resp.error is None
    assert resp.id == 1


def test_parse_response_error():
    raw = {"jsonrpc": "2.0", "error": {"code": -32601, "message": "not found"}, "id": 1}
    resp = parse_response(raw)
    assert resp.result is None
    assert resp.error["code"] == -32601


def test_parse_tool_list():
    data = {
        "result": {
            "tools": [
                {
                    "name": "read_file",
                    "description": "Read a file",
                    "inputSchema": {"type": "object"},
                },
                {"name": "write_file", "description": "Write a file"},
            ],
        },
    }
    tools = parse_tool_list(data)
    assert len(tools) == 2
    assert tools[0].name == "read_file"
    assert tools[1].name == "write_file"


def test_mcp_tool_spec_from_dict():
    data = {
        "name": "test_tool",
        "description": "A test",
        "inputSchema": {"type": "object", "properties": {}},
    }
    spec = MCPToolSpec.from_dict(data)
    assert spec.name == "test_tool"
    assert spec.description == "A test"
    assert spec.input_schema["type"] == "object"


def test_parse_tool_call_result_text():
    data = {
        "result": {
            "content": [
                {"type": "text", "text": "Hello world"},
            ],
        },
    }
    result = parse_tool_call_result(data)
    assert result == "Hello world"


def test_parse_tool_call_result_multiple():
    data = {
        "result": {
            "content": [
                {"type": "text", "text": "Part 1"},
                {"type": "text", "text": "Part 2"},
            ],
        },
    }
    result = parse_tool_call_result(data)
    assert "Part 1" in result
    assert "Part 2" in result


def test_parse_tool_call_result_empty():
    data = {"result": {"content": []}}
    result = parse_tool_call_result(data)
    assert result == ""

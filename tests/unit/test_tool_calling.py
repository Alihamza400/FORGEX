from __future__ import annotations

from forge.core.agent_config import AgentConfig, ToolConfig
from forge.runtime.loop import build_system_prompt, parse_tool_call, strip_tool_call


def test_parse_xml_tool_call():
    text = """Let me search for that.
<tool_call>
<tool>web_search</tool>
<arguments>
{"query": "Python programming"}
</arguments>
</tool_call>
I will now look up the information."""
    result = parse_tool_call(text)
    assert result is not None
    assert result["tool"] == "web_search"
    assert result["args"]["query"] == "Python programming"


def test_parse_tool_call_no_args():
    text = """<tool_call>
<tool>calculator</tool>
<arguments>{}</arguments>
</tool_call>"""
    result = parse_tool_call(text)
    assert result is not None
    assert result["tool"] == "calculator"


def test_no_tool_call():
    result = parse_tool_call("Hello, I'm an AI assistant. How can I help?")
    assert result is None


def test_strip_tool_call():
    text = """Let me think about this.
<tool_call>
<tool>calculator</tool>
<arguments>{"expression": "2+2"}</arguments>
</tool_call>
Based on that, the answer is 4."""
    cleaned = strip_tool_call(text)
    assert "<tool_call>" not in cleaned
    assert "Let me think" in cleaned
    assert "answer is 4" in cleaned


def test_build_system_prompt_with_tools():
    config = AgentConfig(
        name="test",
        role="Researcher",
        goal="Find information",
        tools=[ToolConfig(name="web_search")],
    )
    prompt = build_system_prompt(config)
    assert "Researcher" in prompt
    assert "Find information" in prompt
    assert "web_search" in prompt
    assert "<tool_call>" in prompt
    assert "AVAILABLE TOOLS" in prompt


def test_build_system_prompt_no_tools():
    config = AgentConfig(name="test", role="Chatter", goal="Chat")
    prompt = build_system_prompt(config)
    assert "AVAILABLE TOOLS" not in prompt
    assert "<tool_call>" not in prompt


def test_build_system_prompt_with_extra():
    config = AgentConfig(
        name="test",
        role="Helper",
        goal="Help",
        system_prompt_extra="Always be polite and concise.",
    )
    prompt = build_system_prompt(config)
    assert "Always be polite" in prompt

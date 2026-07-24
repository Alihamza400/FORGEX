from __future__ import annotations

import re
import time
from typing import Any

from forge.core.agent_config import AgentConfig, TaskResult
from forge.core.logging import get_logger
from forge.llm.client import ChatMessage, ModelNotFoundError, OllamaClient, OllamaError
from forge.tools.builtins import register_builtin_tools

logger = get_logger("forge.runtime.loop")

TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*<tool>(.+?)</tool>\s*<arguments>(.*?)</arguments>\s*</tool_call>",
    re.DOTALL,
)

TOOL_CALL_JSON_RE = re.compile(
    r'\{\s*"tool":\s*"(.+?)",\s*"args":\s*(\{.+?\})\s*\}',
    re.DOTALL,
)


def build_system_prompt(config: AgentConfig) -> str:
    lines = [
        f"You are {config.role}.",
        f"Your goal: {config.goal}",
        "",
    ]
    if config.system_prompt_extra:
        lines.append(config.system_prompt_extra)
        lines.append("")

    if config.tools:
        lines.append("AVAILABLE TOOLS:")
        for tool in config.tools:
            lines.append(f"  - {tool.name} ({tool.type})")
        lines.append("")
        lines.append(
            "To use a tool, respond with this format exactly:"
        )
        lines.append("<tool_call>")
        lines.append("<tool>tool_name</tool>")
        lines.append("<arguments>")
        lines.append('{"key": "value"}')
        lines.append("</arguments>")
        lines.append("</tool_call>")
        lines.append("")
        lines.append("After the tool responds, continue with your reasoning.")
        lines.append("")

    if config.memory.type != "none":
        lines.append(
            "You have access to memory from previous conversations. "
            "Relevant context will be provided with each request."
        )
        lines.append("")

    lines.extend([
        "Guidelines:",
        "- Think step by step before answering.",
        "- If you need information, use a tool.",
        "- Be concise and accurate.",
        f"- Maximum iterations: {config.max_iterations}",
    ])

    return "\n".join(lines)


def parse_tool_call(text: str) -> dict[str, Any] | None:
    xml_match = TOOL_CALL_RE.search(text)
    if xml_match:
        tool_name = xml_match.group(1).strip()
        args_raw = xml_match.group(2).strip()
        try:
            import json
            args = json.loads(args_raw) if args_raw else {}
        except json.JSONDecodeError:
            logger.warning("failed to parse tool args as json", raw=args_raw)
            args = {}
        return {"tool": tool_name, "args": args}

    json_match = TOOL_CALL_JSON_RE.search(text)
    if json_match:
        tool_name = json_match.group(1).strip()
        args_raw = json_match.group(2).strip()
        try:
            import json
            args = json.loads(args_raw) if args_raw else {}
        except json.JSONDecodeError:
            args = {}
        return {"tool": tool_name, "args": args}

    return None


def strip_tool_call(text: str) -> str:
    text = TOOL_CALL_RE.sub("", text)
    text = TOOL_CALL_JSON_RE.sub("", text)
    return text.strip()


_tools_registered = False


class AgentLoop:
    def __init__(
        self,
        config: AgentConfig,
        llm_client: OllamaClient | None = None,
    ) -> None:
        global _tools_registered
        if not _tools_registered:
            register_builtin_tools()
            _tools_registered = True

        self.config = config
        self.llm = llm_client or OllamaClient()
        self.system_prompt = build_system_prompt(config)

    async def run(
        self,
        task: str,
        memory_context: str | None = None,
    ) -> TaskResult:
        start_time = time.monotonic()
        messages: list[ChatMessage] = [
            ChatMessage(role="system", content=self.system_prompt),
        ]

        if memory_context:
            messages.append(
                ChatMessage(
                    role="system",
                    content=f"RELEVANT CONTEXT FROM MEMORY:\n{memory_context}",
                )
            )

        messages.append(ChatMessage(role="user", content=task))
        iterations = 0
        total_prompt_tokens = 0
        total_completion_tokens = 0
        last_error: str | None = None

        for iteration in range(self.config.max_iterations):
            iterations = iteration + 1
            logger.debug("agent loop iteration", iteration=iteration, messages=len(messages))

            try:
                result = await self.llm.chat(
                    messages=messages,
                    model=self.config.model.name,
                    temperature=self.config.model.temperature,
                    max_tokens=self.config.model.max_tokens,
                    top_p=self.config.model.top_p,
                )
            except ModelNotFoundError as e:
                last_error = f"Model not found: {e}"
                logger.error("model not found", model=self.config.model.name)
                break
            except OllamaError as e:
                last_error = f"Ollama error: {e}"
                logger.error("ollama error", error=str(e))
                break
            except Exception as e:
                last_error = f"Unexpected error: {e}"
                logger.exception("unexpected error in agent loop")
                break

            total_prompt_tokens += result.prompt_tokens
            total_completion_tokens += result.completion_tokens
            assistant_text = result.text
            messages.append(ChatMessage(role="assistant", content=assistant_text))

            tool_call = parse_tool_call(assistant_text)
            if tool_call is None:
                duration_ms = int((time.monotonic() - start_time) * 1000)
                return TaskResult(
                    agent_name=self.config.name,
                    task=task,
                    output=assistant_text,
                    iterations=iterations,
                    tokens_used=total_prompt_tokens + total_completion_tokens,
                    duration_ms=duration_ms,
                )

            tool_name = tool_call["tool"]
            tool_args = tool_call["args"]
            logger.info("tool call", tool=tool_name, args=tool_args)

            tool_result = await self._execute_tool(tool_name, tool_args)
            messages.append(
                ChatMessage(
                    role="user",
                    content=f"Tool '{tool_name}' returned:\n{tool_result}",
                )
            )

            cleaned = strip_tool_call(assistant_text)
            if cleaned:
                messages[-2] = ChatMessage(role="assistant", content=cleaned)

        duration_ms = int((time.monotonic() - start_time) * 1000)
        last_output = messages[-1].content if messages else ""
        return TaskResult(
            agent_name=self.config.name,
            task=task,
            output=last_output,
            iterations=iterations,
            tokens_used=total_prompt_tokens + total_completion_tokens,
            error=last_error or "Max iterations reached without final answer",
            duration_ms=duration_ms,
        )

    async def _execute_tool(self, tool_name: str, args: dict[str, Any]) -> str:
        from forge.tools.registry import ToolRegistry

        registry = ToolRegistry.get_instance()
        try:
            result = await registry.execute(tool_name, args)
            import json
            return json.dumps(result, indent=2, default=str)
        except Exception as e:
            logger.error("tool execution failed", tool=tool_name, error=str(e))
            return f"Error: {e}"

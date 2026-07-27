from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any

from forge.core.agent_config import AgentConfig, TaskResult
from forge.core.logging import get_logger
from forge.llm.client import ChatMessage, ModelNotFoundError, OllamaClient, OllamaError
from forge.runtime.loop import build_system_prompt, parse_tool_call, strip_tool_call
from forge.tools.builtins import register_builtin_tools

logger = get_logger("forge.runtime.streaming")

_tools_registered = False


async def run_streaming(
    config: AgentConfig,
    task: str,
    llm_client: OllamaClient | None = None,
    memory_context: str | None = None,
) -> AsyncIterator[str]:
    global _tools_registered
    if not _tools_registered:
        register_builtin_tools()
        _tools_registered = True

    llm = llm_client or OllamaClient()
    system_prompt = build_system_prompt(config)
    start_time = time.monotonic()

    messages: list[ChatMessage] = [
        ChatMessage(role="system", content=system_prompt),
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

    for iteration in range(config.max_iterations):
        iterations = iteration + 1
        logger.debug("streaming iteration", iteration=iteration)

        yield _event("iteration", {"iteration": iteration + 1, "max": config.max_iterations})

        try:
            full_text = ""
            async for token in llm.chat_stream(
                messages=messages,
                model=config.model.name,
                temperature=config.model.temperature,
                max_tokens=config.model.max_tokens,
                top_p=config.model.top_p,
            ):
                full_text += token
                yield _event("token", {"token": token})
        except ModelNotFoundError as e:
            last_error = f"Model not found: {e}"
            logger.error("model not found", model=config.model.name)
            yield _event("error", {"error": last_error})
            break
        except OllamaError as e:
            last_error = f"Ollama error: {e}"
            logger.error("ollama error", error=str(e))
            yield _event("error", {"error": last_error})
            break
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            logger.exception("unexpected error in streaming loop")
            yield _event("error", {"error": last_error})
            break

        messages.append(ChatMessage(role="assistant", content=full_text))

        tool_call = parse_tool_call(full_text)
        if tool_call is None:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            result = TaskResult(
                agent_name=config.name,
                task=task,
                output=full_text,
                iterations=iterations,
                tokens_used=total_prompt_tokens + total_completion_tokens,
                duration_ms=duration_ms,
                error=last_error,
            )
            yield _event("done", result.model_dump())
            return

        tool_name = tool_call["tool"]
        tool_args = tool_call["args"]
        logger.info("tool call in stream", tool=tool_name, args=tool_args)
        yield _event("tool_call", {"tool": tool_name, "args": tool_args})

        tool_result = await _execute_tool(tool_name, tool_args)
        yield _event("tool_result", {"tool": tool_name, "result": tool_result})

        messages.append(
            ChatMessage(
                role="user",
                content=f"Tool '{tool_name}' returned:\n{tool_result}",
            )
        )

        cleaned = strip_tool_call(full_text)
        if cleaned:
            messages[-2] = ChatMessage(role="assistant", content=cleaned)

    duration_ms = int((time.monotonic() - start_time) * 1000)
    last_output = messages[-1].content if messages else ""
    result = TaskResult(
        agent_name=config.name,
        task=task,
        output=last_output,
        iterations=iterations,
        tokens_used=total_prompt_tokens + total_completion_tokens,
        error=last_error or "Max iterations reached without final answer",
        duration_ms=duration_ms,
    )
    yield _event("done", result.model_dump())


async def _execute_tool(tool_name: str, args: dict[str, Any]) -> str:
    from forge.tools.registry import ToolRegistry

    registry = ToolRegistry.get_instance()
    try:
        result = await registry.execute(tool_name, args)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error("tool execution failed", tool=tool_name, error=str(e))
        return f"Error: {e}"


def _event(event_type: str, data: dict[str, Any]) -> str:
    return f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"

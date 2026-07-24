from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from forge.orchestrator.models import AgentMessage
from forge.state.redis import RedisState

MessageHandler = Callable[[AgentMessage], None]


class MessageBusError(Exception):
    """Base message bus exception."""


class MessageBus:
    """Agent communication via Redis pub/sub.

    Each agent has a dedicated pub/sub channel for inbox messages.
    Supports request/response correlation, broadcast, and async listeners.
    """

    def __init__(self, state: RedisState) -> None:
        self._state = state
        self._handlers: dict[str, list[MessageHandler]] = {}
        self._listeners: dict[str, asyncio.Task[None]] = {}

    def _inbox(self, agent_name: str) -> str:
        return f"forge:agents:inbox:{agent_name}"

    def _broadcast(self) -> str:
        return "forge:agents:broadcast"

    def _response(self, correlation_id: str) -> str:
        return f"forge:agents:response:{correlation_id}"

    async def send(self, message: AgentMessage) -> None:
        if not message.recipient:
            raise MessageBusError("Message must have a recipient")
        payload = message.model_dump_json()
        channel = self._inbox(message.recipient)
        await self._state.cache_set(channel, payload)
        await self._state.publish_log(message.recipient, "info", payload)

    async def broadcast(self, message: AgentMessage) -> None:
        payload = message.model_dump_json()
        await self._state.publish_log("broadcast", "info", payload)

    async def request(
        self,
        message: AgentMessage,
        response_timeout: float = 30.0,
    ) -> AgentMessage | None:
        if not message.correlation_id:
            message.correlation_id = uuid4().hex[:16]
        await self.send(message)
        start = datetime.now(UTC)
        while (datetime.now(UTC) - start).total_seconds() < response_timeout:
            raw = await self._state.cache_get(self._response(message.correlation_id))
            if raw is not None:
                return AgentMessage.model_validate_json(raw)
            await asyncio.sleep(0.1)
        return None

    async def respond(self, request: AgentMessage, payload: dict[str, Any]) -> None:
        if not request.correlation_id:
            raise MessageBusError("Cannot respond without correlation_id")
        response = AgentMessage(
            type="response",
            sender=request.recipient,
            recipient=request.sender,
            correlation_id=request.correlation_id,
            payload=payload,
        )
        key = self._response(request.correlation_id)
        await self._state.cache_set(key, response.model_dump_json(), ttl_seconds=60)

    def register_handler(self, agent_name: str, handler: MessageHandler) -> None:
        self._handlers.setdefault(agent_name, []).append(handler)

    async def listen(self, agent_name: str) -> AsyncIterator[AgentMessage]:
        async for raw in self._state.subscribe_logs(agent_name):
            try:
                yield AgentMessage.model_validate(raw)
            except Exception:
                continue

    async def start_listener(self, agent_name: str, handler: MessageHandler) -> None:
        async def _loop() -> None:
            async for msg in self.listen(agent_name):
                for h in self._handlers.get(agent_name, [handler]):
                    try:
                        if asyncio.iscoroutinefunction(h):
                            await h(msg)
                        else:
                            h(msg)
                    except Exception:
                        pass

        task = asyncio.create_task(_loop())
        self._listeners[agent_name] = task

    async def stop_listener(self, agent_name: str) -> None:
        task = self._listeners.pop(agent_name, None)
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def close(self) -> None:
        for name in list(self._listeners):
            await self.stop_listener(name)
        self._handlers.clear()

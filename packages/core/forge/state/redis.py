from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import redis.asyncio as aioredis
from forge.core.config import settings
from forge.core.logging import get_logger

logger = get_logger("forge.state.redis")


class RedisError(Exception):
    pass


@dataclass
class TaskItem:
    id: str
    agent_name: str
    task: str
    status: str = "pending"
    created_at: str = ""
    metadata: dict[str, Any] | None = None


class RedisState:
    def __init__(
        self,
        url: str | None = None,
        prefix: str = "forge:",
    ) -> None:
        self.url = url or settings.redis_url
        self.prefix = prefix
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        logger.info("connecting to redis", url=self.url)
        try:
            self._client = aioredis.from_url(  # type: ignore[no-untyped-call]
                self.url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=10,
                retry_on_timeout=True,
            )
            await self._client.ping()
            logger.info("redis connected")
        except Exception as e:
            raise RedisError(f"Failed to connect to Redis: {e}") from e

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("redis connection closed")

    @property
    def client(self) -> aioredis.Redis:
        if self._client is None:
            raise RedisError("Redis not connected. Call connect() first")
        return self._client

    def _key(self, *parts: str) -> str:
        return f"{self.prefix}{':'.join(parts)}"

    def _serialize(self, obj: Any) -> str:
        return json.dumps(obj, default=str)

    def _deserialize(self, data: str | None) -> Any:
        if data is None:
            return None
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return data

    # --- Task Queue ---

    async def push_task(self, queue: str, task: TaskItem) -> str:
        task.id = task.id or str(uuid.uuid4())
        task.created_at = task.created_at or datetime.now(UTC).isoformat()
        key = self._key("queue", queue)
        data = self._serialize(task.__dict__)
        await self.client.rpush(key, data)  # type: ignore[misc]
        logger.debug("pushed task", queue=queue, task_id=task.id)
        return task.id

    async def pop_task(self, queue: str, timeout: int = 5) -> TaskItem | None:
        key = self._key("queue", queue)
        result = await self.client.blpop(key, timeout=timeout)  # type: ignore[arg-type, misc]
        if result is None:
            return None
        _, data = result
        parsed = self._deserialize(data)
        if not parsed:
            return None
        return TaskItem(**parsed)

    async def task_length(self, queue: str) -> int:
        key = self._key("queue", queue)
        return await self.client.llen(key)  # type: ignore[no-any-return, misc]

    # --- Agent State ---

    async def set_state(self, agent_name: str, state: dict[str, Any]) -> None:
        key = self._key("agent", agent_name, "state")
        data = self._serialize(state)
        await self.client.set(key, data)
        await self.client.publish(self._key("pubsub", agent_name), data)
        logger.debug("set agent state", agent=agent_name)

    async def get_state(self, agent_name: str) -> dict[str, Any] | None:
        key = self._key("agent", agent_name, "state")
        data = await self.client.get(key)
        result = self._deserialize(data)
        return result if isinstance(result, dict) else None

    async def watch_state(
        self,
        agent_name: str,
        callback: Callable[[dict[str, Any]], Any],
    ) -> None:
        channel = self._key("pubsub", agent_name)
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = self._deserialize(message["data"])
                    if isinstance(data, dict):
                        await callback(data)
        finally:
            await pubsub.unsubscribe(channel)

    # --- Cache ---

    async def cache_get(self, key: str) -> Any:
        full_key = self._key("cache", key)
        data = await self.client.get(full_key)
        return self._deserialize(data)

    async def cache_set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = 300,
    ) -> None:
        full_key = self._key("cache", key)
        data = self._serialize(value)
        await self.client.setex(full_key, ttl_seconds, data)

    async def cache_delete(self, key: str) -> bool:
        full_key = self._key("cache", key)
        result = await self.client.delete(full_key)
        return result > 0  # type: ignore[no-any-return]

    # --- Log Streaming (Pub/Sub) ---

    async def publish_log(
        self,
        agent_name: str,
        level: str,
        message: str,
    ) -> None:
        channel = self._key("logs", agent_name)
        data = self._serialize({
            "timestamp": datetime.now(UTC).isoformat(),
            "level": level,
            "message": message,
        })
        await self.client.publish(channel, data)

    async def subscribe_logs(
        self,
        agent_name: str,
    ) -> AsyncIterator[dict[str, Any]]:
        channel = self._key("logs", agent_name)
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    parsed = self._deserialize(message["data"])
                    if parsed:
                        yield parsed
        finally:
            await pubsub.unsubscribe(channel)

    # --- Health ---

    async def health(self) -> dict[str, Any]:
        try:
            await self.client.ping()
            try:
                info = await self.client.info(section="server")
                version = info.get("redis_version", "unknown")
            except Exception:
                version = "unknown"
            return {
                "status": "ok",
                "version": version,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

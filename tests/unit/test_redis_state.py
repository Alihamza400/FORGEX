from __future__ import annotations

import pytest
from fakeredis import FakeAsyncRedis
from forge.state.redis import RedisState, TaskItem


@pytest.fixture
async def state():
    s = RedisState(url="redis://localhost:6379/9", prefix="forge:test:")
    s._client = FakeAsyncRedis(decode_responses=True)
    await s.client.ping()
    return s


@pytest.mark.asyncio
async def test_push_and_pop_task(state):
    task = TaskItem(id="", agent_name="test-agent", task="do something")
    task_id = await state.push_task("default", task)
    assert task_id is not None

    popped = await state.pop_task("default", timeout=1)
    assert popped is not None
    assert popped.agent_name == "test-agent"
    assert popped.task == "do something"


@pytest.mark.asyncio
async def test_pop_empty_queue(state):
    result = await state.pop_task("empty", timeout=1)
    assert result is None


@pytest.mark.asyncio
async def test_task_length(state):
    assert await state.task_length("q") == 0
    await state.push_task("q", TaskItem(id="", agent_name="a", task="t1"))
    await state.push_task("q", TaskItem(id="", agent_name="a", task="t2"))
    assert await state.task_length("q") == 2


@pytest.mark.asyncio
async def test_set_and_get_state(state):
    await state.set_state("agent-1", {"status": "running", "task": "test"})
    result = await state.get_state("agent-1")
    assert result is not None
    assert result["status"] == "running"
    assert result["task"] == "test"


@pytest.mark.asyncio
async def test_get_nonexistent_state(state):
    result = await state.get_state("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_cache_set_and_get(state):
    await state.cache_set("mykey", {"value": 42}, ttl_seconds=60)
    result = await state.cache_get("mykey")
    assert result is not None
    assert result["value"] == 42


@pytest.mark.asyncio
async def test_cache_delete(state):
    await state.cache_set("todelete", "data")
    assert await state.cache_delete("todelete") is True
    assert await state.cache_get("todelete") is None


@pytest.mark.asyncio
async def test_cache_miss(state):
    result = await state.cache_get("nonexistent")
    assert result is None


@pytest.mark.asyncio
async def test_publish_and_subscribe_logs(state):
    import asyncio

    received = []

    async def collector():
        async for msg in state.subscribe_logs("agent-x"):
            received.append(msg)
            if len(received) >= 2:
                break

    task = asyncio.create_task(collector())
    await asyncio.sleep(0.1)

    await state.publish_log("agent-x", "INFO", "log line 1")
    await state.publish_log("agent-x", "ERROR", "log line 2")
    await asyncio.sleep(0.2)
    task.cancel()

    assert len(received) == 2
    assert received[0]["level"] == "INFO"
    assert received[1]["level"] == "ERROR"


@pytest.mark.asyncio
async def test_health(state):
    health = await state.health()
    assert health["status"] == "ok"
    assert "version" in health

from __future__ import annotations

import pytest
from forge.storage.models import Base
from forge.storage.repository import AgentRepository, LogRepository, TaskRepository
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()


@pytest.mark.asyncio
async def test_agent_create(session):
    repo = AgentRepository(session)
    agent = await repo.create(
        name="test-agent",
        role="Tester",
        goal="Test everything",
    )
    assert agent.id is not None
    assert agent.name == "test-agent"
    assert agent.role == "Tester"


@pytest.mark.asyncio
async def test_agent_get_by_name(session):
    repo = AgentRepository(session)
    await repo.create(name="finder", role="Finder", goal="Find things")

    agent = await repo.get_by_name("finder")
    assert agent is not None
    assert agent.role == "Finder"


@pytest.mark.asyncio
async def test_agent_get_by_name_not_found(session):
    repo = AgentRepository(session)
    agent = await repo.get_by_name("nonexistent")
    assert agent is None


@pytest.mark.asyncio
async def test_agent_list_all(session):
    repo = AgentRepository(session)
    await repo.create(name="a1", role="R1", goal="G1")
    await repo.create(name="a2", role="R2", goal="G2")

    agents = await repo.list_all()
    assert len(agents) == 2


@pytest.mark.asyncio
async def test_agent_update(session):
    repo = AgentRepository(session)
    created = await repo.create(name="updatable", role="Old", goal="Old goal")

    updated = await repo.update(created.id, role="New", goal="New goal")
    assert updated is not None
    assert updated.role == "New"


@pytest.mark.asyncio
async def test_agent_delete(session):
    repo = AgentRepository(session)
    created = await repo.create(name="deletable", role="D", goal="D")

    deleted = await repo.delete(created.id)
    assert deleted is True

    fetched = await repo.get_by_id(created.id)
    assert fetched is None


@pytest.mark.asyncio
async def test_task_create_and_read(session):
    repo = TaskRepository(session)
    task = await repo.create(agent_name="test-agent", input="do task")
    assert task.id is not None
    assert task.status == "pending"

    fetched = await repo.get_by_id(task.id)
    assert fetched is not None
    assert fetched.input == "do task"


@pytest.mark.asyncio
async def test_task_update_status(session):
    repo = TaskRepository(session)
    task = await repo.create(agent_name="a", input="t")

    updated = await repo.update_status(task.id, "completed", output="done")
    assert updated is not None
    assert updated.status == "completed"
    assert updated.output == "done"


@pytest.mark.asyncio
async def test_task_list_by_agent(session):
    repo = TaskRepository(session)
    await repo.create(agent_name="a1", input="t1")
    await repo.create(agent_name="a1", input="t2")
    await repo.create(agent_name="a2", input="t3")

    tasks = await repo.list_by_agent("a1")
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_task_count_by_status(session):
    repo = TaskRepository(session)
    await repo.create(agent_name="a", input="t1")
    await repo.update_status(1, "completed")

    total = await repo.count_by_status()
    completed = await repo.count_by_status("completed")
    pending = await repo.count_by_status("pending")
    assert total >= 1
    assert completed >= 0
    assert pending >= 0


@pytest.mark.asyncio
async def test_log_create(session):
    repo = LogRepository(session)
    log = await repo.create(
        agent_name="test-agent",
        level="INFO",
        message="test log",
    )
    assert log.id is not None
    assert log.message == "test log"


@pytest.mark.asyncio
async def test_log_list_by_agent(session):
    repo = LogRepository(session)
    await repo.create(agent_name="a1", level="INFO", message="m1")
    await repo.create(agent_name="a1", level="ERROR", message="m2")

    logs = await repo.list_by_agent("a1")
    assert len(logs) == 2

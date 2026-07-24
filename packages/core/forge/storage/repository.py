from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from forge.core.logging import get_logger
from forge.storage.models import AgentModel, LogModel, RunModel, TaskModel
from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("forge.storage.repository")


class AgentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, name: str, role: str, goal: str, **kwargs: Any) -> AgentModel:
        agent = AgentModel(name=name, role=role, goal=goal, **kwargs)
        self.session.add(agent)
        await self.session.commit()
        await self.session.refresh(agent)
        logger.info("created agent", id=agent.id, name=agent.name)
        return agent

    async def get_by_id(self, agent_id: int) -> AgentModel | None:
        result = await self.session.execute(
            select(AgentModel).where(AgentModel.id == agent_id),
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> AgentModel | None:
        result = await self.session.execute(
            select(AgentModel).where(AgentModel.name == name),
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[AgentModel]:
        result = await self.session.execute(
            select(AgentModel).order_by(desc(AgentModel.updated_at)),
        )
        return list(result.scalars().all())

    async def update(self, agent_id: int, **kwargs: Any) -> AgentModel | None:
        kwargs["updated_at"] = datetime.now(UTC)
        await self.session.execute(
            update(AgentModel).where(AgentModel.id == agent_id).values(**kwargs),
        )
        await self.session.commit()
        return await self.get_by_id(agent_id)

    async def delete(self, agent_id: int) -> bool:
        result = await self.session.execute(
            delete(AgentModel).where(AgentModel.id == agent_id),
        )
        await self.session.commit()
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, agent_name: str, input: str, **kwargs: Any) -> TaskModel:
        task = TaskModel(agent_name=agent_name, input=input, **kwargs)
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        logger.info("created task", id=task.id, agent=task.agent_name)
        return task

    async def get_by_id(self, task_id: int) -> TaskModel | None:
        result = await self.session.execute(
            select(TaskModel).where(TaskModel.id == task_id),
        )
        return result.scalar_one_or_none()

    async def list_by_agent(
        self,
        agent_name: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TaskModel]:
        result = await self.session.execute(
            select(TaskModel)
            .where(TaskModel.agent_name == agent_name)
            .order_by(desc(TaskModel.created_at))
            .limit(limit)
            .offset(offset),
        )
        return list(result.scalars().all())

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> list[TaskModel]:
        query = select(TaskModel)
        if status:
            query = query.where(TaskModel.status == status)
        query = query.order_by(desc(TaskModel.created_at)).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_status(
        self,
        task_id: int,
        status: str,
        **kwargs: Any,
    ) -> TaskModel | None:
        values: dict[str, Any] = {"status": status, **kwargs}
        if status in ("completed", "failed"):
            values["finished_at"] = datetime.now(UTC)
        await self.session.execute(
            update(TaskModel).where(TaskModel.id == task_id).values(**values),
        )
        await self.session.commit()
        return await self.get_by_id(task_id)

    async def count_by_status(self, status: str | None = None) -> int:
        query = select(func.count(TaskModel.id))
        if status:
            query = query.where(TaskModel.status == status)
        result = await self.session.execute(query)
        return result.scalar() or 0


class LogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        agent_name: str,
        level: str,
        message: str,
        **kwargs: Any,
    ) -> LogModel:
        log = LogModel(agent_name=agent_name, level=level, message=message, **kwargs)
        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log

    async def list_by_agent(
        self,
        agent_name: str,
        limit: int = 100,
        offset: int = 0,
        level: str | None = None,
    ) -> list[LogModel]:
        query = select(LogModel).where(LogModel.agent_name == agent_name)
        if level:
            query = query.where(LogModel.level == level)
        query = query.order_by(desc(LogModel.timestamp)).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def list_by_task(
        self,
        task_id: int,
        limit: int = 200,
    ) -> list[LogModel]:
        result = await self.session.execute(
            select(LogModel)
            .where(LogModel.task_id == task_id)
            .order_by(LogModel.timestamp)
            .limit(limit),
        )
        return list(result.scalars().all())


class RunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, agent_id: int, agent_name: str, **kwargs: Any) -> RunModel:
        run = RunModel(agent_id=agent_id, agent_name=agent_name, **kwargs)
        self.session.add(run)
        await self.session.commit()
        await self.session.refresh(run)
        return run

    async def get_by_id(self, run_id: int) -> RunModel | None:
        result = await self.session.execute(
            select(RunModel).where(RunModel.id == run_id),
        )
        return result.scalar_one_or_none()

    async def update(self, run_id: int, **kwargs: Any) -> RunModel | None:
        if "finished_at" in kwargs or kwargs.get("status") in ("completed", "failed"):
            kwargs["finished_at"] = datetime.now(UTC)
        await self.session.execute(
            update(RunModel).where(RunModel.id == run_id).values(**kwargs),
        )
        await self.session.commit()
        return await self.get_by_id(run_id)

    async def list_by_agent(
        self,
        agent_id: int,
        limit: int = 50,
    ) -> list[RunModel]:
        result = await self.session.execute(
            select(RunModel)
            .where(RunModel.agent_id == agent_id)
            .order_by(desc(RunModel.started_at))
            .limit(limit),
        )
        return list(result.scalars().all())

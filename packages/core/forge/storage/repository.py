from __future__ import annotations

from datetime import datetime
from typing import Any

from forge.core.logging import get_logger
from forge.storage.models import AgentModel, AgentTemplateModel, LogModel, McpServerModel, RunModel, TaskModel, WebhookModel, _utcnow
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
        kwargs["updated_at"] = _utcnow()
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
            values["finished_at"] = _utcnow()
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
            kwargs["finished_at"] = _utcnow()
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


class McpServerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        name: str,
        transport_type: str,
        url: str | None = None,
        command: str | None = None,
        cwd: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> McpServerModel:
        server = McpServerModel(
            name=name,
            transport_type=transport_type,
            url=url,
            command=command,
            cwd=cwd,
            config=config,
        )
        self.session.add(server)
        await self.session.commit()
        await self.session.refresh(server)
        logger.info("created mcp server", id=server.id, name=server.name)
        return server

    async def get_by_id(self, server_id: int) -> McpServerModel | None:
        result = await self.session.execute(
            select(McpServerModel).where(McpServerModel.id == server_id),
        )
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str) -> McpServerModel | None:
        result = await self.session.execute(
            select(McpServerModel).where(McpServerModel.name == name),
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[McpServerModel]:
        result = await self.session.execute(
            select(McpServerModel).order_by(desc(McpServerModel.updated_at)),
        )
        return list(result.scalars().all())

    async def update_status(self, server_id: int, status: str) -> McpServerModel | None:
        values: dict[str, Any] = {"status": status, "updated_at": _utcnow()}
        await self.session.execute(
            update(McpServerModel).where(McpServerModel.id == server_id).values(**values),
        )
        await self.session.commit()
        return await self.get_by_id(server_id)

    async def delete(self, server_id: int) -> bool:
        result = await self.session.execute(
            delete(McpServerModel).where(McpServerModel.id == server_id),
        )
        await self.session.commit()
        return result.rowcount > 0


class AgentTemplateRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        name: str,
        config_json: dict[str, Any],
        description: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
    ) -> AgentTemplateModel:
        tmpl = AgentTemplateModel(
            name=name,
            description=description,
            config_json=config_json,
            category=category,
            tags=tags,
        )
        self.session.add(tmpl)
        await self.session.commit()
        await self.session.refresh(tmpl)
        logger.info("created agent template", id=tmpl.id, name=tmpl.name)
        return tmpl

    async def get_by_id(self, tmpl_id: int) -> AgentTemplateModel | None:
        result = await self.session.execute(
            select(AgentTemplateModel).where(AgentTemplateModel.id == tmpl_id),
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AgentTemplateModel]:
        query = select(AgentTemplateModel)
        if category:
            query = query.where(AgentTemplateModel.category == category)
        query = query.order_by(desc(AgentTemplateModel.usage_count)).limit(limit).offset(offset)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update(
        self,
        tmpl_id: int,
        **kwargs: Any,
    ) -> AgentTemplateModel | None:
        kwargs["updated_at"] = _utcnow()
        await self.session.execute(
            update(AgentTemplateModel).where(AgentTemplateModel.id == tmpl_id).values(**kwargs),
        )
        await self.session.commit()
        return await self.get_by_id(tmpl_id)

    async def increment_usage(self, tmpl_id: int) -> AgentTemplateModel | None:
        await self.session.execute(
            update(AgentTemplateModel)
            .where(AgentTemplateModel.id == tmpl_id)
            .values(usage_count=AgentTemplateModel.usage_count + 1, updated_at=_utcnow()),
        )
        await self.session.commit()
        return await self.get_by_id(tmpl_id)

    async def delete(self, tmpl_id: int) -> bool:
        result = await self.session.execute(
            delete(AgentTemplateModel).where(AgentTemplateModel.id == tmpl_id),
        )
        await self.session.commit()
        return result.rowcount > 0


class WebhookRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        name: str,
        url: str,
        events: list[str] | None = None,
        secret: str | None = None,
        active: int = 1,
    ) -> WebhookModel:
        hook = WebhookModel(
            name=name,
            url=url,
            events=events or ["agent.run.completed"],
            secret=secret,
            active=active,
        )
        self.session.add(hook)
        await self.session.commit()
        await self.session.refresh(hook)
        logger.info("created webhook", id=hook.id, name=hook.name)
        return hook

    async def get_by_id(self, hook_id: int) -> WebhookModel | None:
        result = await self.session.execute(
            select(WebhookModel).where(WebhookModel.id == hook_id),
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> list[WebhookModel]:
        result = await self.session.execute(
            select(WebhookModel).order_by(desc(WebhookModel.created_at)),
        )
        return list(result.scalars().all())

    async def get_active_by_event(self, event: str) -> list[WebhookModel]:
        result = await self.session.execute(
            select(WebhookModel)
            .where(WebhookModel.active == 1)
            .order_by(desc(WebhookModel.created_at)),
        )
        return [h for h in result.scalars().all() if event in (h.events or [])]

    async def update(
        self,
        hook_id: int,
        **kwargs: Any,
    ) -> WebhookModel | None:
        kwargs["updated_at"] = _utcnow()
        await self.session.execute(
            update(WebhookModel).where(WebhookModel.id == hook_id).values(**kwargs),
        )
        await self.session.commit()
        return await self.get_by_id(hook_id)

    async def delete(self, hook_id: int) -> bool:
        result = await self.session.execute(
            delete(WebhookModel).where(WebhookModel.id == hook_id),
        )
        await self.session.commit()
        return result.rowcount > 0

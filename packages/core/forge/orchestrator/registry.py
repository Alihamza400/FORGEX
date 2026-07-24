from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from forge.orchestrator.exceptions import AgentNotFoundError
from forge.orchestrator.models import AgentCapability, AgentDescriptor, AgentStatus


class AgentRegistry:
    """Thread-safe registry of available agents with capability-based discovery."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentDescriptor] = {}
        self._timeout_seconds: int = 60

    def register(
        self,
        name: str,
        role: str,
        goal: str = "",
        capabilities: list[AgentCapability | str] | None = None,
        endpoint: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentDescriptor:
        parsed_caps: list[AgentCapability] = []
        for c in capabilities or []:
            if isinstance(c, AgentCapability):
                parsed_caps.append(c)
            else:
                try:
                    parsed_caps.append(AgentCapability(c))
                except ValueError:
                    continue

        descriptor = AgentDescriptor(
            name=name,
            role=role,
            goal=goal,
            capabilities=parsed_caps,
            status=AgentStatus.IDLE,
            last_heartbeat=datetime.now(UTC),
            endpoint=endpoint,
            metadata=metadata or {},
        )
        self._agents[name] = descriptor
        return descriptor

    def deregister(self, name: str) -> None:
        self._agents.pop(name, None)

    def get(self, name: str) -> AgentDescriptor:
        agent = self._agents.get(name)
        if agent is None:
            raise AgentNotFoundError(f"Agent '{name}' not found")
        return agent

    def list(self) -> list[AgentDescriptor]:
        return list(self._agents.values())

    def find_by_capability(
        self,
        capability: AgentCapability | str,
        status: AgentStatus | None = AgentStatus.IDLE,
    ) -> list[AgentDescriptor]:
        if isinstance(capability, str):
            try:
                capability = AgentCapability(capability)
            except ValueError:
                return []

        results: list[AgentDescriptor] = []
        for agent in self._agents.values():
            if status and agent.status != status:
                continue
            if capability in agent.capabilities:
                results.append(agent)
        return results

    def find_by_role(
        self,
        role: str,
        status: AgentStatus | None = AgentStatus.IDLE,
    ) -> list[AgentDescriptor]:
        results: list[AgentDescriptor] = []
        for agent in self._agents.values():
            if status and agent.status != status:
                continue
            if role.lower() in agent.role.lower():
                results.append(agent)
        return results

    def update_status(self, name: str, status: AgentStatus) -> AgentDescriptor:
        agent = self.get(name)
        agent.status = status
        if status == AgentStatus.IDLE:
            agent.last_heartbeat = datetime.now(UTC)
        return agent

    def heartbeat(self, name: str) -> AgentDescriptor:
        agent = self.get(name)
        agent.last_heartbeat = datetime.now(UTC)
        return agent

    def health_check(self, name: str) -> bool:
        try:
            agent = self.get(name)
            if agent.last_heartbeat is None:
                return False
            elapsed = (datetime.now(UTC) - agent.last_heartbeat).total_seconds()
            return elapsed < self._timeout_seconds
        except AgentNotFoundError:
            return False

    def prune_stale(self) -> list[str]:
        now = datetime.now(UTC)
        stale: list[str] = []
        for name, agent in list(self._agents.items()):
            if agent.last_heartbeat is None:  # noqa: SIM114
                stale.append(name)
            elif (now - agent.last_heartbeat).total_seconds() > self._timeout_seconds:  # noqa: SIM114
                stale.append(name)
        for name in stale:
            self.deregister(name)
        return stale

    def count(self) -> int:
        return len(self._agents)

    def clear(self) -> None:
        self._agents.clear()


_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def reset_registry() -> None:
    global _registry
    _registry = None

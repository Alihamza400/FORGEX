from __future__ import annotations

import pytest
from forge.orchestrator.exceptions import (
    AgentNotFoundError,
    OrchestratorError,
)
from forge.orchestrator.models import (
    AgentCapability,
    AgentDescriptor,
    AgentMessage,
    AgentStatus,
    OrchestrationConfig,
    OrchestrationResult,
    OrchestrationStrategy,
    SubTaskDef,
    SubTaskResult,
    SubTaskStatus,
)
from forge.orchestrator.registry import AgentRegistry, get_registry, reset_registry


# ── Fixtures ───────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def reset_registry_fixture():
    reset_registry()
    yield
    reset_registry()
@pytest.fixture
def registry() -> AgentRegistry:
    return get_registry()
# ── Agent Registry Tests ──────────────────────────────────────────────
class TestAgentRegistry:
    def test_register(self, registry: AgentRegistry):
        desc = registry.register(
            name="test-agent",
            role="Research Analyst",
            goal="Find information",
            capabilities=[AgentCapability.SEARCH],
        )
        assert desc.name == "test-agent"
        assert desc.role == "Research Analyst"
        assert AgentCapability.SEARCH in desc.capabilities
        assert desc.status == AgentStatus.IDLE
    def test_register_with_string_capabilities(self, registry: AgentRegistry):
        desc = registry.register(
            name="agent-2",
            role="Coder",
            capabilities=["code"],
        )
        assert AgentCapability.CODE in desc.capabilities
    def test_deregister(self, registry: AgentRegistry):
        registry.register("a1", "Test Agent")
        registry.deregister("a1")
        with pytest.raises(AgentNotFoundError):
            registry.get("a1")
    def test_get_not_found(self, registry: AgentRegistry):
        with pytest.raises(AgentNotFoundError):
            registry.get("nonexistent")
    def test_list(self, registry: AgentRegistry):
        registry.register("a1", "Role 1")
        registry.register("a2", "Role 2")
        agents = registry.list_agents()
        assert len(agents) == 2
    def test_find_by_capability(self, registry: AgentRegistry):
        registry.register("a1", "Search Agent", capabilities=[AgentCapability.SEARCH])
        registry.register("a2", "Code Agent", capabilities=[AgentCapability.CODE])
        registry.register(
            "a3", "Both Agent",
            capabilities=[AgentCapability.SEARCH, AgentCapability.CODE],
        )
        results = registry.find_by_capability(AgentCapability.SEARCH)
        assert len(results) == 2
        assert all(AgentCapability.SEARCH in a.capabilities for a in results)
    def test_find_by_capability_respects_status(self, registry: AgentRegistry):
        registry.register("a1", "Search Agent", capabilities=[AgentCapability.SEARCH])
        registry.update_status("a1", AgentStatus.BUSY)
        results = registry.find_by_capability(AgentCapability.SEARCH, status=AgentStatus.IDLE)
        assert len(results) == 0
        results = registry.find_by_capability(AgentCapability.SEARCH, status=AgentStatus.BUSY)
        assert len(results) == 1
    def test_find_by_role(self, registry: AgentRegistry):
        registry.register("a1", "Research Analyst")
        registry.register("a2", "Code Developer")
        registry.register("a3", "Senior Research Analyst")
        results = registry.find_by_role("research")
        assert len(results) == 2
        assert all("research" in a.role.lower() for a in results)
    def test_update_status(self, registry: AgentRegistry):
        registry.register("a1", "Agent 1")
        desc = registry.update_status("a1", AgentStatus.BUSY)
        assert desc.status == AgentStatus.BUSY
    def test_health_check(self, registry: AgentRegistry):
        registry.register("a1", "Agent 1")
        assert registry.health_check("a1") is True
        assert registry.health_check("nonexistent") is False
    def test_prune_stale(self, registry: AgentRegistry):
        registry.register("a1", "Agent 1")
        # after prune, a1 should be healthy (just registered)
        stale = registry.prune_stale()
        assert len(stale) == 0
    def test_count(self, registry: AgentRegistry):
        assert registry.count() == 0
        registry.register("a1", "Role")
        assert registry.count() == 1
    def test_clear(self, registry: AgentRegistry):
        registry.register("a1", "Role")
        registry.clear()
        assert registry.count() == 0
# ── Model Tests ───────────────────────────────────────────────────────
class TestModels:
    def test_orchestration_config_defaults(self):
        config = OrchestrationConfig(agent_roles=["researcher"])
        assert config.strategy == OrchestrationStrategy.AUTO
        assert config.max_concurrency == 3
        assert config.timeout_seconds == 600
        assert config.token_budget == 100_000
        assert config.fallback_behavior.value == "error"
    def test_orchestration_config_validation(self):
        config = OrchestrationConfig(
            agent_roles=["coder"],
            strategy="supervisor",
            max_concurrency=5,
        )
        assert config.strategy == OrchestrationStrategy.SUPERVISOR
    def test_sub_task_def_dependencies(self):
        sub = SubTaskDef(
            description="Do something",
            depends_on=["task-1", "task-2"],
            agent_capabilities=[AgentCapability.REASONING],
        )
        assert len(sub.depends_on) == 2
        assert AgentCapability.REASONING in sub.agent_capabilities
    def test_sub_task_result_status_transition(self):
        result = SubTaskResult(
            sub_task_id="st-1",
            description="Test sub-task",
            status=SubTaskStatus.COMPLETED,
            agent_name="agent-1",
            output="Done",
        )
        assert result.status == SubTaskStatus.COMPLETED
    def test_agent_message_creates_id(self):
        msg = AgentMessage(sender="agent-1", recipient="agent-2")
        assert len(msg.id) == 16
        assert msg.type == "request"
    def test_agent_message_with_payload(self):
        msg = AgentMessage(
            sender="a1",
            recipient="a2",
            type="response",
            payload={"result": "success"},
        )
        assert msg.payload["result"] == "success"
    def test_orchestration_result_accumulation(self):
        result = OrchestrationResult(
            task="Test task",
            strategy=OrchestrationStrategy.SEQUENTIAL,
            status=SubTaskStatus.RUNNING,
        )
        assert result.id is not None
        assert result.total_tokens == 0
    def test_agent_descriptor_defaults(self):
        desc = AgentDescriptor(name="agent-1", role="Worker")
        assert desc.status == AgentStatus.IDLE
        assert desc.goal == ""
        assert desc.capabilities == []
    def test_agent_descriptor_status_enum(self):
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.BUSY.value == "busy"
        assert AgentStatus.ERROR.value == "error"
        assert AgentStatus.OFFLINE.value == "offline"
    def test_orchestration_strategies(self):
        assert OrchestrationStrategy.SEQUENTIAL.value == "sequential"
        assert OrchestrationStrategy.PARALLEL.value == "parallel"
        assert OrchestrationStrategy.SUPERVISOR.value == "supervisor"
        assert OrchestrationStrategy.AUTO.value == "auto"
# ── Error Tests ───────────────────────────────────────────────────────
class TestOrchestratorErrors:
    def test_base_error(self):
        with pytest.raises(OrchestratorError):
            raise OrchestratorError("base error")
    def test_agent_not_found(self):
        with pytest.raises(AgentNotFoundError):
            raise AgentNotFoundError("not found")
        assert issubclass(AgentNotFoundError, OrchestratorError)

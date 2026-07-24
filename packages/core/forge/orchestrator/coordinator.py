from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime

from forge.core.agent_config import AgentConfig
from forge.llm.client import OllamaClient
from forge.orchestrator.exceptions import (
    OrchestrationTimeoutError,
    TokenBudgetExceededError,
)
from forge.orchestrator.models import (
    AgentStatus,
    FallbackBehavior,
    OrchestrationConfig,
    OrchestrationResult,
    OrchestrationStrategy,
    SubTaskDef,
    SubTaskResult,
    SubTaskStatus,
)
from forge.orchestrator.planner import TaskPlanner
from forge.orchestrator.registry import AgentRegistry
from forge.runtime.agent import AgentRuntime


class OrchestratorCoordinator:
    """Executes a decomposed task DAG across multiple agents.

    Supports sequential, parallel, and supervisor execution strategies.
    Manages concurrency, timeouts, token budgets, and failure recovery.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        registry: AgentRegistry,
        planner: TaskPlanner,
        agents: dict[str, AgentConfig],
    ) -> None:
        self._llm = llm_client
        self._registry = registry
        self._planner = planner
        self._agents = agents
        self._total_tokens: int = 0

    async def orchestrate(
        self,
        task: str,
        config: OrchestrationConfig,
    ) -> OrchestrationResult:
        start_time = time.monotonic()
        result = OrchestrationResult(
            task=task,
            strategy=config.strategy,
            status=SubTaskStatus.RUNNING,
        )

        try:
            sub_tasks = await self._planner.plan(task, config)
            sub_tasks = self._resolve_agents(sub_tasks, config)
            strategy = self._resolve_strategy(sub_tasks, config)

            result.strategy = strategy

            if strategy == OrchestrationStrategy.SUPERVISOR:
                sub_results = await self._run_supervisor(task, sub_tasks, config)
            elif strategy == OrchestrationStrategy.PARALLEL:
                sub_results = await self._run_parallel(sub_tasks, config)
            else:
                sub_results = await self._run_sequential(sub_tasks, config)

            result.sub_results = sub_results
            result.status = SubTaskStatus.COMPLETED

            for sr in sub_results:
                result.total_iterations += sr.iterations
                result.total_tokens += sr.tokens_used
                result.total_duration_ms = max(result.total_duration_ms, sr.duration_ms)
                if sr.error:
                    result.status = SubTaskStatus.FAILED

            if result.status == SubTaskStatus.COMPLETED:
                result.final_output = self._consolidate_outputs(sub_results)

        except OrchestrationTimeoutError:
            result.status = SubTaskStatus.FAILED
            result.error = "Orchestration timed out"
        except TokenBudgetExceededError as e:
            result.status = SubTaskStatus.FAILED
            result.error = str(e)
        except Exception as e:
            result.status = SubTaskStatus.FAILED
            result.error = f"Orchestration failed: {e}"

        result.total_tokens = self._total_tokens
        result.total_duration_ms = int((time.monotonic() - start_time) * 1000)
        result.finished_at = datetime.now(UTC)
        return result

    def _resolve_strategy(
        self,
        sub_tasks: list[SubTaskDef],
        config: OrchestrationConfig,
    ) -> OrchestrationStrategy:
        if config.strategy != OrchestrationStrategy.AUTO:
            return config.strategy

        has_deps = any(t.depends_on for t in sub_tasks)
        if config.enable_supervisor and len(sub_tasks) > 2:
            return OrchestrationStrategy.SUPERVISOR
        if config.enable_parallel and not has_deps and len(sub_tasks) > 1:
            return OrchestrationStrategy.PARALLEL
        return OrchestrationStrategy.SEQUENTIAL

    def _resolve_agents(
        self,
        sub_tasks: list[SubTaskDef],
        config: OrchestrationConfig,  # noqa: ARG002
    ) -> list[SubTaskDef]:
        for task_def in sub_tasks:
            if task_def.agent_role and not task_def.agent_capabilities:
                agents = self._registry.find_by_role(task_def.agent_role)
                if agents:
                    task_def.agent_capabilities = agents[0].capabilities
        return sub_tasks

    async def _run_sequential(
        self,
        sub_tasks: list[SubTaskDef],
        config: OrchestrationConfig,
    ) -> list[SubTaskResult]:
        results: list[SubTaskResult] = []
        completed: dict[str, str] = {}

        for task_def in self._topological_sort(sub_tasks):
            ctx = self._build_context(task_def, results, completed)
            sr = await self._execute_sub_task(task_def, ctx, config)
            results.append(sr)
            if sr.status == SubTaskStatus.COMPLETED and sr.output:
                completed[task_def.id] = sr.output

            await self._check_budget(sr, config)
            if sr.status == SubTaskStatus.FAILED:
                if config.fallback_behavior == FallbackBehavior.ERROR:
                    break
                if config.fallback_behavior == FallbackBehavior.RETRY:
                    sr = await self._retry(task_def, ctx, config)
                    results[-1] = sr
                    if sr.status == SubTaskStatus.COMPLETED:
                        completed[task_def.id] = sr.output

        return results

    async def _run_parallel(
        self,
        sub_tasks: list[SubTaskDef],
        config: OrchestrationConfig,
    ) -> list[SubTaskResult]:
        semaphore = asyncio.Semaphore(config.max_concurrency)

        async def _run_one(task_def: SubTaskDef) -> SubTaskResult:
            async with semaphore:
                ctx = ""
                sr = await self._execute_sub_task(task_def, ctx, config)
                await self._check_budget(sr, config)
                return sr

        tasks = [_run_one(t) for t in sub_tasks]
        return list(await asyncio.gather(*tasks, return_exceptions=False))

    async def _run_supervisor(
        self,
        task: str,
        sub_tasks: list[SubTaskDef],
        config: OrchestrationConfig,
    ) -> list[SubTaskResult]:
        from forge.orchestrator.supervisor import SupervisorOrchestrator

        supervisor = SupervisorOrchestrator(
            llm_client=self._llm,
            registry=self._registry,
            agents=self._agents,
        )
        return await supervisor.run(task, sub_tasks, config)

    async def _execute_sub_task(
        self,
        task_def: SubTaskDef,
        context: str,
        config: OrchestrationConfig,
    ) -> SubTaskResult:
        start = time.monotonic()
        started_at = datetime.now(UTC)

        sr = SubTaskResult(
            sub_task_id=task_def.id,
            description=task_def.description,
            status=SubTaskStatus.RUNNING,
            started_at=started_at,
        )

        try:
            timeout = task_def.timeout_seconds or config.timeout_seconds
            agent_name = await self._select_agent(task_def)
            sr.agent_name = agent_name

            if not agent_name:
                sr.status = SubTaskStatus.FAILED
                sr.error = "No suitable agent available"
                sr.finished_at = datetime.now(UTC)
                sr.duration_ms = int((time.monotonic() - start) * 1000)
                return sr

            agent_cfg = self._agents.get(agent_name)
            if agent_cfg is None:
                sr.status = SubTaskStatus.FAILED
                sr.error = f"Agent '{agent_name}' config not found"
                sr.finished_at = datetime.now(UTC)
                sr.duration_ms = int((time.monotonic() - start) * 1000)
                return sr

            self._registry.update_status(agent_name, AgentStatus.BUSY)

            full_task = task_def.description
            if context:
                full_task = f"Context:\n{context}\n\nTask:\n{task_def.description}"

            runtime = AgentRuntime(config=agent_cfg, llm_client=self._llm)
            try:
                await runtime.initialize()
                agent_result = await asyncio.wait_for(
                    runtime.run(full_task),
                    timeout=timeout,
                )
                sr.output = agent_result.output
                sr.tokens_used = agent_result.tokens_used
                sr.iterations = agent_result.iterations
                sr.status = SubTaskStatus.COMPLETED
                if agent_result.error:
                    sr.status = SubTaskStatus.FAILED
                    sr.error = agent_result.error
            finally:
                await runtime.close()
                self._registry.update_status(agent_name, AgentStatus.IDLE)

        except TimeoutError:
            sr.status = SubTaskStatus.FAILED
            sr.error = f"Sub-task timed out after {timeout}s"
        except Exception as e:
            sr.status = SubTaskStatus.FAILED
            sr.error = f"Execution error: {e}"

        sr.duration_ms = int((time.monotonic() - start) * 1000)
        sr.finished_at = datetime.now(UTC)
        return sr

    async def _select_agent(self, task_def: SubTaskDef) -> str:
        if task_def.agent_capabilities:
            for cap in task_def.agent_capabilities:
                agents = self._registry.find_by_capability(cap)
                if agents:
                    return agents[0].name

        if task_def.agent_role:
            agents = self._registry.find_by_role(task_def.agent_role)
            if agents:
                return agents[0].name

        available = [k for k, v in self._agents.items()
                     if self._registry.health_check(k)]
        return available[0] if available else ""

    async def _retry(
        self,
        task_def: SubTaskDef,
        context: str,
        config: OrchestrationConfig,
    ) -> SubTaskResult:
        for attempt in range(3):
            sr = await self._execute_sub_task(task_def, context, config)
            if sr.status == SubTaskStatus.COMPLETED:
                return sr
            await asyncio.sleep(2 ** attempt)
        sr.status = SubTaskStatus.FAILED
        sr.error = f"{sr.error} (after 3 retries)"
        return sr

    async def _check_budget(
        self,
        sr: SubTaskResult,
        config: OrchestrationConfig,
    ) -> None:
        self._total_tokens += sr.tokens_used
        if self._total_tokens > config.token_budget:
            raise TokenBudgetExceededError(
                f"Token budget {config.token_budget} exceeded "
                f"({self._total_tokens} used)"
            )

    def _build_context(
        self,
        task_def: SubTaskDef,
        results: list[SubTaskResult],  # noqa: ARG002
        completed: dict[str, str],
    ) -> str:
        parts: list[str] = []
        for dep_id in task_def.depends_on:
            output = completed.get(dep_id)
            if output:
                parts.append(f"[Previous sub-task result]\n{output}")
        return "\n\n".join(parts)

    def _consolidate_outputs(self, results: list[SubTaskResult]) -> str:
        parts: list[str] = []
        for r in results:
            if r.output:
                parts.append(
                    f"## {r.description}\n{r.output}\n"
                )
        return "\n---\n".join(parts)

    def _topological_sort(self, sub_tasks: list[SubTaskDef]) -> list[SubTaskDef]:
        graph: dict[str, set[str]] = {}
        names: dict[str, SubTaskDef] = {}
        for t in sub_tasks:
            graph[t.id] = set(t.depends_on)
            names[t.id] = t

        sorted_tasks: list[SubTaskDef] = []
        visited: set[str] = set()

        def _visit(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            for dep in graph.get(node_id, set()):
                _visit(dep)
            if node_id in names:
                sorted_tasks.append(names[node_id])

        for t in sub_tasks:
            _visit(t.id)

        return sorted_tasks

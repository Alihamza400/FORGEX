from __future__ import annotations

import time
from datetime import UTC, datetime

from forge.core.agent_config import AgentConfig
from forge.llm.client import OllamaClient
from forge.orchestrator.coordinator import OrchestratorCoordinator
from forge.orchestrator.models import (
    OrchestrationConfig,
    SubTaskDef,
    SubTaskResult,
    SubTaskStatus,
)
from forge.orchestrator.registry import AgentRegistry

SUPERVISOR_SYSTEM_PROMPT = """You are an AI supervisor orchestrating a team of specialized agents.

Your role:
1. **Plan** — decompose the user's task into clear steps
2. **Delegate** — assign each step to the right agent based on their capabilities
3. **Review** — examine each agent's output for quality and correctness
4. **Consolidate** — combine all results into a coherent final answer

Available agents and their roles:
{agent_descriptions}

Execution flow:
- You will receive each sub-task result one at a time
- Review the output before considering it complete
- If unsatisfactory, provide specific feedback for improvement
- Once all sub-tasks are complete, synthesize the final answer

Rules:
- Be specific in your feedback
- Do not repeat work already completed
- Focus on synthesis and quality control
- Keep the final answer comprehensive and well-structured"""


class SupervisorOrchestrator:
    """Supervisor agent pattern: plans, delegates, reviews, and consolidates.

    A single supervisor LLM session coordinates the entire workflow,
    directing specialised agents and reviewing their outputs.
    """

    def __init__(
        self,
        llm_client: OllamaClient,
        registry: AgentRegistry,
        agents: dict[str, AgentConfig],
    ) -> None:
        self._llm = llm_client
        self._registry = registry
        self._agents = agents
        self._coordinator = OrchestratorCoordinator(
            llm_client=llm_client,
            registry=registry,
            planner=None,  # type: ignore[arg-type]
            agents=agents,
        )

    async def run(
        self,
        task: str,
        sub_tasks: list[SubTaskDef],
        config: OrchestrationConfig,
    ) -> list[SubTaskResult]:
        agent_descriptions = self._build_agent_descriptions()
        system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
            agent_descriptions=agent_descriptions,
        )

        results: list[SubTaskResult] = []
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Task to orchestrate:\n\n{task}"},
        ]

        for i, task_def in enumerate(sub_tasks):
            start = time.monotonic()
            started_at = datetime.now(UTC)

            sr = SubTaskResult(
                sub_task_id=task_def.id,
                description=task_def.description,
                status=SubTaskStatus.PENDING,
                started_at=started_at,
            )

            # Delegate to the coordinator for execution
            delegate_sr = await self._delegate(task_def, config)

            sr.agent_name = delegate_sr.agent_name
            sr.status = delegate_sr.status
            sr.output = delegate_sr.output
            sr.error = delegate_sr.error
            sr.iterations = delegate_sr.iterations
            sr.tokens_used = delegate_sr.tokens_used
            sr.started_at = delegate_sr.started_at

            # Review via supervisor LLM
            if sr.status == SubTaskStatus.COMPLETED:
                review_prompt = (
                    f"Sub-task {i+1}/{len(sub_tasks)}: {task_def.description}\n\n"
                    f"Agent: {sr.agent_name}\n\n"
                    f"Output:\n{sr.output}\n\n"
                    "Review this output. Is it complete and correct? "
                    "If yes, respond with 'APPROVED: <brief summary>'. "
                    "If no, explain what needs improvement."
                )
                messages.append({"role": "user", "content": review_prompt})
                try:
                    review = await self._llm.chat(
                        messages=messages,  # type: ignore[arg-type]
                        model="llama3.2:3b",
                        temperature=0.3,
                        max_tokens=1024,
                    )
                    messages.append({"role": "assistant", "content": review.text})

                    if not review.text.strip().upper().startswith("APPROVED"):
                        rework_sr = await self._rework(task_def, review.text, config)
                        if rework_sr.status == SubTaskStatus.COMPLETED:
                            sr.output = rework_sr.output
                            sr.iterations += rework_sr.iterations
                            sr.tokens_used += rework_sr.tokens_used
                except Exception:
                    pass  # Accept output if review fails

            sr.duration_ms = int((time.monotonic() - start) * 1000)
            sr.finished_at = datetime.now(UTC)
            results.append(sr)

            # Consolidation step for the supervisor
            consolidation_prompt = self._build_consolidation_prompt(sr, results)
            messages.append({"role": "user", "content": consolidation_prompt})

        # Final consolidation
        if results:
            try:
                final_prompt = (
                    "All sub-tasks are complete. "
                    "Provide a comprehensive final answer that synthesizes all results."
                )
                messages.append({"role": "user", "content": final_prompt})
                final = await self._llm.chat(
                    messages=messages,  # type: ignore[arg-type]
                    model="llama3.2:3b",
                    temperature=0.3,
                    max_tokens=4096,
                )
                if final.text:
                    results[-1].output += f"\n\n**Supervisor Synthesis:**\n{final.text}"
            except Exception:
                pass

        return results

    async def _delegate(
        self,
        task_def: SubTaskDef,
        config: OrchestrationConfig,
    ) -> SubTaskResult:
        """Delegate a sub-task to the most suitable agent."""
        return await self._coordinator._execute_sub_task(task_def, "", config)

    async def _rework(
        self,
        task_def: SubTaskDef,
        feedback: str,
        config: OrchestrationConfig,
    ) -> SubTaskResult:
        """Re-execute with supervisor feedback as context."""
        task_def.description = (
            f"{task_def.description}\n\nSupervisor feedback: {feedback}"
        )
        return await self._delegate(task_def, config)

    def _build_agent_descriptions(self) -> str:
        parts: list[str] = []
        for name, cfg in self._agents.items():
            desc = self._registry.get(name) if self._registry._agents.get(name) else None
            caps = ", ".join(c.value for c in desc.capabilities) if desc else "general"
            parts.append(f"- {name}: {cfg.role} [capabilities: {caps}]")
        return "\n".join(parts)

    def _build_consolidation_prompt(
        self,
        sr: SubTaskResult,
        results: list[SubTaskResult],
    ) -> str:
        completed = sum(1 for r in results if r.status == SubTaskStatus.COMPLETED)
        total = len(results)
        status = "passed" if sr.status == SubTaskStatus.COMPLETED else "failed"
        return (
            f"Sub-task '{sr.description}' {status}. "
            f"Progress: {completed}/{total} complete. "
            f"Continue orchestrating the remaining sub-tasks."
        )

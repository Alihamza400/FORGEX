from __future__ import annotations

import json
import re

from forge.llm.client import OllamaClient
from forge.orchestrator.exceptions import TaskDecompositionError
from forge.orchestrator.models import (
    AgentCapability,
    OrchestrationConfig,
    SubTaskDef,
)
from forge.orchestrator.registry import AgentRegistry


class TaskPlanner:
    """Decomposes a complex task into a dependency graph of sub-tasks.

    Uses an LLM to analyse the task and produce a structured plan.
    Falls back to a single flat task if the LLM is unavailable.
    """

    PLAN_PROMPT = """Decompose the following task into sub-tasks executable by AI agents.

Task: {task}
Agent roles available: {roles}
Agent capabilities available: {capabilities}

For each sub-task, provide:
1. A clear description of what needs to be done
2. The agent capability required (search, analysis, code, writing, reasoning, summarization)
3. Any sub-tasks it depends on (by index, 0-based)
4. Priority (0-100, higher = more important)

Respond with ONLY valid JSON in the following format:
{{
  "sub_tasks": [
    {{
      "description": "...",
      "agent_capabilities": ["search"],
      "depends_on": [0],
      "priority": 80
    }}
  ]
}}

Rules:
- Break into 1-8 sub-tasks
- Independent sub-tasks can run in parallel
- Be specific in descriptions
- Include dependencies accurately
"""

    def __init__(
        self,
        llm_client: OllamaClient,
        registry: AgentRegistry,
        model: str = "llama3.2:3b",
    ) -> None:
        self._llm = llm_client
        self._registry = registry
        self._model = model

    async def plan(
        self,
        task: str,
        config: OrchestrationConfig,
    ) -> list[SubTaskDef]:
        """Decompose task into sub-tasks using LLM.

        Falls back to a single sub-task if LLM fails or planning is disabled.
        """
        if not config.enable_task_planning:
            return self._fallback_plan(task, config)

        roles = ", ".join(config.agent_roles) if config.agent_roles else "any"
        capabilities = ", ".join(c.value for c in AgentCapability)

        prompt = self.PLAN_PROMPT.format(
            task=task,
            roles=roles,
            capabilities=capabilities,
        )

        try:
            result = await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                model=self._model,
                temperature=0.2,
                max_tokens=4096,
            )
            return self._parse_plan(result.text, config)
        except Exception as e:
            raise TaskDecompositionError(f"LLM planning failed: {e}") from e

    def _parse_plan(self, text: str, config: OrchestrationConfig) -> list[SubTaskDef]:
        try:
            json_str = self._extract_json(text)
            data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError) as e:
            raise TaskDecompositionError(f"Invalid JSON from planner: {e}") from e

        tasks = data.get("sub_tasks", [])
        if not tasks:
            raise TaskDecompositionError("Planner returned empty sub-tasks list")

        sub_tasks: list[SubTaskDef] = []
        for i, item in enumerate(tasks):
            caps_raw = item.get("agent_capabilities", [])
            caps: list[AgentCapability] = []
            for c in caps_raw:
                if isinstance(c, str):
                    try:
                        caps.append(AgentCapability(c.lower()))
                    except ValueError:
                        continue

            sub_tasks.append(SubTaskDef(
                description=item.get("description", f"Sub-task {i}"),
                agent_capabilities=caps or [AgentCapability.REASONING],
                depends_on=item.get("depends_on", []),
                priority=item.get("priority", 0),
                max_iterations=config.max_iterations_per_agent,
                timeout_seconds=min(config.timeout_seconds, 300),
            ))

        return sub_tasks

    def _extract_json(self, text: str) -> str:
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            return json_match.group(0)
        raise TaskDecompositionError("No JSON object found in planner response")

    def _fallback_plan(
        self,
        task: str,
        config: OrchestrationConfig,
    ) -> list[SubTaskDef]:
        return [
            SubTaskDef(
                description=task,
                agent_capabilities=[],
                depends_on=[],
                priority=50,
                max_iterations=config.max_iterations_per_agent,
                timeout_seconds=min(config.timeout_seconds, 300),
            ),
        ]

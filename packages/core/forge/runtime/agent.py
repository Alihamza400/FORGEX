from __future__ import annotations

from forge.core.agent_config import AgentConfig, TaskResult
from forge.core.logging import get_logger
from forge.llm.client import OllamaClient
from forge.memory.memory_manager import MemoryManager
from forge.runtime.loop import AgentLoop
from forge.tools.builtins.filesystem import set_workspace

logger = get_logger("forge.runtime.agent")


class AgentRuntime:
    def __init__(
        self,
        config: AgentConfig,
        llm_client: OllamaClient | None = None,
    ) -> None:
        self.config = config
        self.loop = AgentLoop(config=config, llm_client=llm_client)
        self.memory = MemoryManager(
            config=config.memory,
            llm_client=llm_client,
        )

    async def initialize(self) -> None:
        await self.memory.initialize()

    async def run(self, task: str) -> TaskResult:
        if self.config.workspace_dir:
            set_workspace(self.config.workspace_dir)
            logger.info("set agent workspace", workspace=self.config.workspace_dir)

        logger.info(
            "running agent",
            agent=self.config.name,
            task_len=len(task),
            memory_type=self.config.memory.type,
        )

        memory_context = ""
        if self.config.memory.type != "none":
            memory_context = await self.memory.retrieve_context(task)
            if memory_context:
                logger.info(
                    "retrieved memory context",
                    agent=self.config.name,
                    context_len=len(memory_context),
                )

        result = await self.loop.run(task=task, memory_context=memory_context)

        if self.config.memory.type != "none" and result.output:
            await self.memory.store_conversation(
                agent_name=self.config.name,
                messages=[
                    {"role": "user", "content": task},
                    {"role": "assistant", "content": result.output},
                ],
            )

        logger.info(
            "agent finished",
            agent=self.config.name,
            iterations=result.iterations,
            error=result.error is not None,
            duration_ms=result.duration_ms,
        )
        return result

    async def close(self) -> None:
        await self.memory.close()
        if hasattr(self.loop.llm, "close"):
            await self.loop.llm.close()

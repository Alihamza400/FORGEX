from __future__ import annotations

from datetime import UTC
from typing import Any

from forge.core.agent_config import MemoryConfig
from forge.core.logging import get_logger
from forge.llm.client import OllamaClient
from forge.memory.qdrant import QdrantMemory

logger = get_logger("forge.memory.manager")


class MemoryError(Exception):
    pass


class MemoryManager:
    def __init__(
        self,
        config: MemoryConfig,
        llm_client: OllamaClient | None = None,
    ) -> None:
        self.config = config
        self.llm = llm_client or OllamaClient()
        self._store: QdrantMemory | None = None

    async def initialize(self) -> None:
        if self.config.type == "qdrant":
            self._store = QdrantMemory(
                collection=self.config.collection,
            )
            self._store.connect()
            logger.info(
                "memory manager initialized",
                type=self.config.type,
                collection=self.config.collection,
            )
        elif self.config.type == "none":
            logger.info("memory disabled")
        else:
            logger.warning("unsupported memory type", type=self.config.type)

    async def close(self) -> None:
        if self._store:
            self._store.close()
        await self.llm.close()

    async def store_conversation(
        self,
        agent_name: str,
        messages: list[dict[str, str]],
    ) -> int:
        if self._store is None:
            return 0

        try:
            texts = [
                f"{m.get('role', 'unknown')}: {m.get('content', '')}"
                for m in messages
                if m.get("content")
            ]
            if not texts:
                return 0

            combined = "\n".join(texts)
            embedding = await self.llm.embeddings(
                combined,
                model=self.config.embedding_model,
            )

            if not embedding:
                logger.warning("empty embedding, skipping storage")
                return 0

            from datetime import datetime

            point_id = f"{agent_name}:{datetime.now(UTC).isoformat()}"
            self._store.upsert([
                (
                    point_id,
                    embedding,
                    {
                        "agent": agent_name,
                        "text": combined,
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                ),
            ])
            return 1
        except Exception as e:
            logger.error("failed to store conversation", error=str(e))
            return 0

    async def retrieve_context(
        self,
        query: str,
        limit: int | None = None,
    ) -> str:
        if self._store is None:
            return ""

        limit = limit or self.config.top_k
        try:
            embedding = await self.llm.embeddings(
                query,
                model=self.config.embedding_model,
            )
            if not embedding:
                return ""

            results = self._store.search(
                vector=embedding,
                limit=limit,
                score_threshold=self.config.score_threshold,
            )

            if not results:
                return ""

            context_parts = []
            for r in results:
                text = r.payload.get("text", "")
                agent = r.payload.get("agent", "unknown")
                score = r.score
                if text:
                    context_parts.append(f"[{agent} (relevance: {score:.2f})]\n{text}")

            return "\n\n".join(context_parts)
        except Exception as e:
            logger.error("failed to retrieve context", error=str(e))
            return ""

    async def clear_memory(self, agent_name: str | None = None) -> int:
        if self._store is None:
            return 0
        try:
            if agent_name:
                self._store.delete_by_filter({
                    "must": [
                        {"key": "agent", "match": {"value": agent_name}},
                    ],
                })
            else:
                old_count = self._store.count()
                import math

                for _ in range(math.ceil(old_count / 100)):
                    results = self._store.search(
                        vector=[0.0] * 768,
                        limit=100,
                    )
                    if not results:
                        break
                    self._store.delete([r.id for r in results])

            logger.info("cleared memory", agent=agent_name)
            return 1
        except Exception as e:
            logger.error("failed to clear memory", error=str(e))
            return 0

    async def health(self) -> dict[str, Any]:
        if self._store:
            return self._store.health()
        return {"status": "disabled", "type": "none"}

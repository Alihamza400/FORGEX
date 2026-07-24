from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from forge.core.config import settings
from forge.core.logging import get_logger
from qdrant_client import QdrantClient as SyncQdrantClient
from qdrant_client.http import models as qmodels
from qdrant_client.http.exceptions import UnexpectedResponse

logger = get_logger("forge.memory.qdrant")


class QdrantError(Exception):
    pass


class CollectionNotFoundError(QdrantError):
    pass


@dataclass
class SearchResult:
    id: str
    score: float
    payload: dict[str, Any]
    vector: list[float] | None = None


class QdrantMemory:
    def __init__(
        self,
        url: str | None = None,
        collection: str = "default",
        vector_size: int = 768,
        timeout_seconds: int = 30,
    ) -> None:
        self.url = url or settings.qdrant_url
        self.collection = collection
        self.vector_size = vector_size
        self.timeout_seconds = timeout_seconds
        self._client: SyncQdrantClient | None = None

    def connect(self) -> None:
        logger.info("connecting to qdrant", url=self.url, collection=self.collection)
        try:
            self._client = SyncQdrantClient(
                url=self.url,
                timeout=self.timeout_seconds,
            )
            self._ensure_collection()
            logger.info("qdrant connected", collection=self.collection)
        except Exception as e:
            raise QdrantError(f"Failed to connect to Qdrant: {e}") from e

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            logger.info("qdrant connection closed")

    @property
    def client(self) -> SyncQdrantClient:
        if self._client is None:
            self.connect()
        return self._client  # type: ignore[return-value]

    def _ensure_collection(self) -> None:
        try:
            collections = self.client.get_collections().collections
            existing = {c.name for c in collections}

            if self.collection not in existing:
                logger.info(
                    "creating qdrant collection",
                    collection=self.collection,
                    vector_size=self.vector_size,
                )
                self.client.create_collection(
                    collection_name=self.collection,
                    vectors_config=qmodels.VectorParams(
                        size=self.vector_size,
                        distance=qmodels.Distance.COSINE,
                    ),
                )
        except UnexpectedResponse as e:
            raise QdrantError(f"Failed to ensure collection: {e}") from e

    def upsert(
        self,
        points: list[tuple[str, list[float], dict[str, Any]]],
    ) -> int:
        if not points:
            return 0

        try:
            qdrant_points = [
                qmodels.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
                for point_id, vector, payload in points
            ]
            self.client.upsert(
                collection_name=self.collection,
                points=qdrant_points,
                wait=True,
            )
            logger.debug(
                "upserted qdrant points",
                collection=self.collection,
                count=len(points),
            )
            return len(points)
        except Exception as e:
            raise QdrantError(f"Failed to upsert points: {e}") from e

    def search(
        self,
        vector: list[float],
        limit: int = 5,
        score_threshold: float | None = None,
        filter_: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        try:
            qfilter = None
            if filter_:
                qfilter = qmodels.Filter(**filter_)

            results = self.client.search(  # type: ignore[attr-defined]
                collection_name=self.collection,
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold,
                query_filter=qfilter,
            )

            parsed = [
                SearchResult(
                    id=str(r.id),
                    score=r.score,
                    payload=r.payload or {},
                    vector=r.vector if isinstance(r.vector, list) else None,
                )
                for r in results
            ]
            logger.debug(
                "searched qdrant",
                collection=self.collection,
                limit=limit,
                hits=len(parsed),
            )
            return parsed
        except Exception as e:
            raise QdrantError(f"Failed to search Qdrant: {e}") from e

    def delete(self, point_ids: list[str]) -> int:
        if not point_ids:
            return 0
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=qmodels.PointIdsList(points=point_ids),  # type: ignore[arg-type]
                wait=True,
            )
            logger.debug("deleted qdrant points", count=len(point_ids))
            return len(point_ids)
        except Exception as e:
            raise QdrantError(f"Failed to delete points: {e}") from e

    def delete_by_filter(self, filter_: dict[str, Any]) -> int:
        try:
            self.client.delete(
                collection_name=self.collection,
                points_selector=qmodels.FilterSelector(
                    filter=qmodels.Filter(**filter_),
                ),
                wait=True,
            )
            logger.debug("deleted qdrant points by filter")
            return 1
        except Exception as e:
            raise QdrantError(f"Failed to delete by filter: {e}") from e

    def count(self) -> int:
        try:
            result = self.client.count(collection_name=self.collection)
            return result.count
        except Exception as e:
            raise QdrantError(f"Failed to count points: {e}") from e

    def health(self) -> dict[str, Any]:
        try:
            info = self.client.get_collections()
            count = self.count()
            return {
                "status": "ok",
                "collection": self.collection,
                "point_count": count,
                "collections": [c.name for c in info.collections],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from forge.memory.qdrant import QdrantMemory


@pytest.fixture
def mock_qdrant_client():
    with patch("forge.memory.qdrant.SyncQdrantClient") as mock:
        instance = MagicMock()
        mock.return_value = instance
        instance.get_collections.return_value.collections = []
        yield instance
@pytest.fixture
def memory(mock_qdrant_client):
    m = QdrantMemory(url="http://test:6333", collection="test-collection", vector_size=768)
    m._client = mock_qdrant_client
    return m
def test_connect_creates_collection(mock_qdrant_client):
    memory = QdrantMemory(url="http://test:6333", collection="new-collection")
    memory._client = mock_qdrant_client
    memory._ensure_collection()
    mock_qdrant_client.create_collection.assert_called_once()
def test_upsert_points(memory, mock_qdrant_client):
    points = [
        ("id-1", [0.1] * 768, {"text": "hello"}),
        ("id-2", [0.2] * 768, {"text": "world"}),
    ]
    count = memory.upsert(points)
    assert count == 2
    mock_qdrant_client.upsert.assert_called_once()
def test_search(memory, mock_qdrant_client):
    mock_qdrant_client.search.return_value = [
        MagicMock(id="id-1", score=0.95, payload={"text": "result"}, vector=None),
    ]
    results = memory.search(vector=[0.1] * 768, limit=5)
    assert len(results) == 1
    assert results[0].id == "id-1"
    assert results[0].score == 0.95
    assert results[0].payload["text"] == "result"
def test_search_with_threshold(memory, mock_qdrant_client):
    mock_qdrant_client.search.return_value = []
    results = memory.search(
        vector=[0.1] * 768,
        limit=3,
        score_threshold=0.7,
    )
    assert len(results) == 0
    mock_qdrant_client.search.assert_called_once()
def test_delete_points(memory, mock_qdrant_client):
    count = memory.delete(["id-1", "id-2"])
    assert count == 2
    mock_qdrant_client.delete.assert_called_once()
def test_count(memory, mock_qdrant_client):
    mock_qdrant_client.count.return_value.count = 42
    assert memory.count() == 42
def test_health_ok(memory, mock_qdrant_client):
    mock_qdrant_client.get_collections.return_value.collections = []
    mock_qdrant_client.count.return_value.count = 10
    health = memory.health()
    assert health["status"] == "ok"
    assert health["point_count"] == 10
def test_health_error(memory, mock_qdrant_client):
    mock_qdrant_client.get_collections.side_effect = Exception("connection failed")
    health = memory.health()
    assert health["status"] == "error"
    assert "connection failed" in health["error"]

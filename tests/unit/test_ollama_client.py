from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from forge.llm.client import (
    ChatMessage,
    ModelNotFoundError,
    OllamaClient,
    OllamaError,
)


@pytest.fixture
def client():
    c = OllamaClient(base_url="http://test:11434", timeout_seconds=5, max_retries=0)
    yield c
@pytest.mark.asyncio
async def test_list_models(client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.content = b'{"models": [{"name": "llama3.2:3b"}]}'
    with patch.object(client._client, "request", return_value=mock_response):
        models = await client.list_models()
        assert len(models) == 1
        assert models[0]["name"] == "llama3.2:3b"
@pytest.mark.asyncio
async def test_chat_basic(client):
    response_data = {
        "model": "llama3.2:3b",
        "message": {"content": "Hello! How can I help?"},
        "prompt_eval_count": 10,
        "eval_count": 5,
    }
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.content = str(response_data).replace("'", '"').encode()
    with patch.object(client._client, "request", return_value=mock_response):
        result = await client.chat(
            messages=[ChatMessage(role="user", content="Hi")],
            model="llama3.2:3b",
        )
        assert "Hello" in result.text
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 5
@pytest.mark.asyncio
async def test_generate(client):
    response_data = {
        "model": "llama3.2:3b",
        "response": "The answer is 42.",
        "prompt_eval_count": 8,
        "eval_count": 12,
    }
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.content = str(response_data).replace("'", '"').encode()
    with patch.object(client._client, "request", return_value=mock_response):
        result = await client.generate(prompt="What is 6*7?", model="llama3.2:3b")
        assert "42" in result.text
        assert result.model == "llama3.2:3b"
@pytest.mark.asyncio
async def test_embeddings(client):
    response_data = {
        "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],
    }
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.content = str(response_data).replace("'", '"').encode()
    with patch.object(client._client, "request", return_value=mock_response):
        emb = await client.embeddings("test text")
        assert len(emb) == 5
        assert emb[0] == 0.1
@pytest.mark.asyncio
async def test_model_not_found(client):
    mock_response = AsyncMock(spec=httpx.Response)
    mock_response.status_code = 404
    mock_response.url = "http://test:11434/api/chat"
    with (
        patch.object(client._client, "request", return_value=mock_response),
        pytest.raises(ModelNotFoundError),
    ):
        await client.chat(
            messages=[ChatMessage(role="user", content="Hi")],
            model="nonexistent",
        )
@pytest.mark.asyncio
async def test_retry_on_failure(client):
    client.max_retries = 1
    fail_response = AsyncMock(spec=httpx.Response)
    fail_response.status_code = 502
    fail_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "502", request=AsyncMock(), response=fail_response,
    )
    success_response = AsyncMock(spec=httpx.Response)
    success_response.status_code = 200
    success_response.content = b'{"models": [{"name": "test"}]}'
    mock_request = AsyncMock()
    mock_request.side_effect = [fail_response, success_response]
    with patch.object(client._client, "request", mock_request):
        models = await client.list_models()
        assert len(models) == 1
        assert mock_request.call_count == 2
@pytest.mark.asyncio
async def test_all_retries_exhausted(client):
    client.max_retries = 1
    fail_response = AsyncMock(spec=httpx.Response)
    fail_response.status_code = 502
    fail_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "502", request=AsyncMock(), response=fail_response,
    )
    mock_request = AsyncMock(return_value=fail_response)
    with patch.object(client._client, "request", mock_request), pytest.raises(OllamaError):
        await client.chat(
            messages=[ChatMessage(role="user", content="Hi")],
            model="test",
        )

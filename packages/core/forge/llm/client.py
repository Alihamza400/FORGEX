from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
from forge.core.config import settings
from forge.core.logging import get_logger
from httpx import HTTPStatusError, RequestError, TimeoutException

logger = get_logger("forge.llm.client")


class OllamaError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)


class ModelNotFoundError(OllamaError):
    pass


@dataclass
class ChatMessage:
    role: str
    content: str
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class GenerationResult:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_duration_ns: int = 0


def _parse_json(data: str | bytes) -> dict[str, Any]:
    try:
        import orjson

        return orjson.loads(data)
    except ImportError:
        import json

        return json.loads(data)


class OllamaClient:
    def __init__(
        self,
        base_url: str | None = None,
        timeout_seconds: int = 120,
        max_retries: int = 2,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout_seconds),
            follow_redirects=True,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def list_models(self) -> list[dict[str, Any]]:
        response = await self._get("/api/tags")
        data = _parse_json(response.content)
        models = data.get("models", [])
        logger.info("listed ollama models", count=len(models))
        return models

    async def generate(
        self,
        prompt: str,
        model: str = "",
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.9,
    ) -> GenerationResult:
        model_name = model or settings.ollama_default_model
        payload: dict[str, Any] = {
            "model": model_name,
            "prompt": prompt,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": top_p,
            },
            "stream": False,
        }
        if system:
            payload["system"] = system

        logger.debug(
            "ollama generate",
            model=model_name,
            prompt_len=len(prompt),
        )

        response = await self._post("/api/generate", payload)
        data = _parse_json(response.content)
        return GenerationResult(
            text=data.get("response", ""),
            model=data.get("model", model_name),
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            total_duration_ns=data.get("total_duration", 0),
        )

    async def chat(
        self,
        messages: list[ChatMessage],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.9,
    ) -> GenerationResult:
        return await self._chat(messages, model, temperature, max_tokens, top_p, stream=False)

    def chat_stream(
        self,
        messages: list[ChatMessage],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        top_p: float = 0.9,
    ) -> AsyncIterator[str]:
        return self._chat_stream(messages, model, temperature, max_tokens, top_p)

    async def embeddings(
        self,
        text: str,
        model: str = "nomic-embed-text",
    ) -> list[float]:
        payload = {"model": model, "prompt": text}
        response = await self._post("/api/embeddings", payload)
        data = _parse_json(response.content)
        embedding = data.get("embedding", [])
        logger.debug(
            "ollama embeddings",
            model=model,
            text_len=len(text),
            dim=len(embedding),
        )
        return embedding

    async def pull_model(self, model: str) -> dict[str, Any]:
        logger.info("pulling ollama model", model=model)
        response = await self._post("/api/pull", {"model": model, "stream": False})
        return _parse_json(response.content)

    async def _chat(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        stream: bool,
    ) -> GenerationResult:
        model_name = model or settings.ollama_default_model
        payload = self._build_chat_payload(
            messages, model_name, temperature, max_tokens, top_p, stream,
        )

        logger.debug("ollama chat", model=model_name, messages=len(messages))

        if stream:
            return await self._chat_stream_to_result(payload, model_name)

        response = await self._post("/api/chat", payload)
        data = _parse_json(response.content)
        message = data.get("message", {})
        return GenerationResult(
            text=message.get("content", ""),
            model=data.get("model", model_name),
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            total_duration_ns=data.get("total_duration", 0),
        )

    async def _chat_stream(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> AsyncIterator[str]:
        model_name = model or settings.ollama_default_model
        payload = self._build_chat_payload(
            messages, model_name, temperature, max_tokens, top_p, True,
        )

        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            self._check_response(response)
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk = _parse_json(line)
                content = chunk.get("message", {}).get("content", "")
                if content:
                    yield content

    async def _chat_stream_to_result(
        self,
        payload: dict[str, Any],
        model_name: str,
    ) -> GenerationResult:
        full_text = ""
        async with self._client.stream("POST", "/api/chat", json=payload) as response:
            self._check_response(response)
            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                chunk = _parse_json(line)
                full_text += chunk.get("message", {}).get("content", "")
                if chunk.get("done", False):
                    prompt_tokens = chunk.get("prompt_eval_count", 0)
                    completion_tokens = chunk.get("eval_count", 0)
                    return GenerationResult(
                        text=full_text,
                        model=model_name,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_duration_ns=chunk.get("total_duration", 0),
                    )
        return GenerationResult(text=full_text, model=model_name)

    def _build_chat_payload(
        self,
        messages: list[ChatMessage],
        model: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        stream: bool,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": top_p,
            },
            "stream": stream,
        }

    async def _get(self, path: str) -> httpx.Response:
        return await self._request("GET", path)

    async def _post(self, path: str, json: dict[str, Any] | None = None) -> httpx.Response:
        return await self._request("POST", path, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> httpx.Response:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self._client.request(method, path, json=json)
                self._check_response(response)
                return response
            except ModelNotFoundError:
                raise
            except HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise ModelNotFoundError(
                        f"Model not found at {path}",
                        status_code=404,
                    ) from e
                last_error = e
                logger.warning(
                    "ollama http error",
                    path=path,
                    status=e.response.status_code,
                    attempt=attempt + 1,
                )
            except TimeoutException as e:
                last_error = e
                logger.warning("ollama timeout", path=path, attempt=attempt + 1)
            except RequestError as e:
                last_error = e
                logger.warning(
                    "ollama request error",
                    path=path,
                    error=str(e),
                    attempt=attempt + 1,
                )

            if attempt < self.max_retries:
                import asyncio

                wait = 1.0 * (attempt + 1)
                logger.info("retrying ollama request", path=path, wait=wait)
                await asyncio.sleep(wait)

        raise OllamaError(
            f"Request failed after {self.max_retries + 1} attempts: {last_error}",
        )

    def _check_response(self, response: httpx.Response) -> None:
        if response.status_code == 404:
            raise ModelNotFoundError(
                f"Model not found: {response.url}",
                status_code=404,
            )
        response.raise_for_status()

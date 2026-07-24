from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

import httpx
from forge.core.logging import get_logger

logger = get_logger("forge.tools.mcp_transport")


class MCPTransportError(Exception):
    pass


class MCPTransport(ABC):
    @abstractmethod
    async def connect(self) -> None:
        ...

    @abstractmethod
    async def send(self, message: dict[str, Any]) -> None:
        ...

    @abstractmethod
    async def receive(self) -> dict[str, Any] | None:
        ...

    @abstractmethod
    async def close(self) -> None:
        ...


class StdioTransport(MCPTransport):
    def __init__(self, command: list[str], cwd: str | None = None) -> None:
        self.command = command
        self.cwd = cwd
        self._process: asyncio.subprocess.Process | None = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._buf = ""

    async def connect(self) -> None:
        logger.info("starting mcp stdio transport", command=" ".join(self.command))
        self._process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.cwd,
        )

        if self._process.stdout is None or self._process.stdin is None:
            raise MCPTransportError("Failed to create stdio pipes")

        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await self._process.stdout.connect_read_pipe(protocol)

        transport, _ = await asyncio.get_running_loop().connect_write_pipe(
            lambda: asyncio.Protocol(),
            self._process.stdin,
        )
        self._writer = transport.get_extra_info("writer")  # type: ignore[union-attr]

        logger.info("mcp stdio transport connected", pid=self._process.pid)

    async def send(self, message: dict[str, Any]) -> None:
        if self._writer is None:
            raise MCPTransportError("Transport not connected")
        line = json.dumps(message) + "\n"
        self._writer.write(line.encode("utf-8"))
        await self._writer.drain()

    async def receive(self) -> dict[str, Any] | None:
        if self._reader is None:
            raise MCPTransportError("Transport not connected")

        while True:
            if "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    return json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning("failed to parse mcp message", error=str(e))
                    continue

            chunk = await self._reader.read(4096)
            if not chunk:
                return None

            chunk_str = chunk.decode("utf-8")
            self._buf += chunk_str

    async def close(self) -> None:
        if self._process is None:
            return
        logger.info("closing mcp stdio transport")
        try:
            self._process.terminate()
            await asyncio.wait_for(self._process.wait(), timeout=5)
        except TimeoutError:
            logger.warning("mcp process did not terminate, killing")
            self._process.kill()
            await self._process.wait()
        except ProcessLookupError:
            pass


class HTTPTransport(MCPTransport):
    def __init__(self, url: str, timeout_seconds: int = 30) -> None:
        self.url = url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        self._event_source: httpx.Response | None = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
        )
        logger.info("mcp http transport connected", url=self.url)

    async def send(self, message: dict[str, Any]) -> None:
        if self._client is None:
            raise MCPTransportError("Transport not connected")
        response = await self._client.post(
            f"{self.url}/messages",
            json=message,
        )
        response.raise_for_status()

    async def receive(self) -> dict[str, Any] | None:
        if self._event_source is None:
            self._event_source = await self._client.get(  # type: ignore[union-attr]
                f"{self.url}/events",
                headers={"Accept": "text/event-stream"},
            )

        if self._event_source is None:
            raise MCPTransportError("Transport not connected")

        buf = ""
        async for line in self._event_source.aiter_lines():
            if line.startswith("data: "):
                data = line[6:].strip()
                if data:
                    try:
                        return json.loads(data)
                    except json.JSONDecodeError as e:
                        logger.warning("failed to parse SSE data", error=str(e))
            elif line == "" and buf:
                try:
                    return json.loads(buf)
                except json.JSONDecodeError:
                    pass
                buf = ""
            else:
                buf += line

        return None

    async def close(self) -> None:
        if self._event_source:
            await self._event_source.aclose()
        if self._client:
            await self._client.aclose()
        logger.info("mcp http transport closed")

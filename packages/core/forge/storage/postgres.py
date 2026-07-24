from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from forge.core.config import settings
from forge.core.logging import get_logger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = get_logger("forge.storage.postgres")


class PostgresError(Exception):
    pass


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str | None = None) -> None:
        self.url = url or settings.database_url
        self._engine = None
        self._session_factory = None

    async def connect(self) -> None:
        logger.info("connecting to database", url=self.url)
        try:
            kwargs: dict[str, Any] = {"echo": False}
            if self.url.startswith("postgresql"):
                kwargs["pool_size"] = 5
                kwargs["max_overflow"] = 10
                kwargs["pool_pre_ping"] = True
            self._engine = create_async_engine(self.url, **kwargs)
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            async with self._engine.connect() as conn:
                await conn.run_sync(lambda _: None)
            logger.info("postgres connected")
        except Exception as e:
            raise PostgresError(f"Failed to connect to Postgres: {e}") from e

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            logger.info("postgres connection closed")

    async def create_all(self) -> None:
        async with self._engine.begin() as conn:  # type: ignore[union-attr]
            await conn.run_sync(Base.metadata.create_all)

    async def drop_all(self) -> None:
        async with self._engine.begin() as conn:  # type: ignore[union-attr]
            await conn.run_sync(Base.metadata.drop_all)

    def session(self) -> AsyncIterator[AsyncSession]:
        return self._session_factory()  # type: ignore[return-value]

    async def health(self) -> dict[str, Any]:
        try:
            async with self.session() as session:
                await session.execute(
                    __import__("sqlalchemy").text("SELECT 1"),
                )
            return {"status": "ok", "database": "postgresql"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

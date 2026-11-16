from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from vortemis.infrastructure.persistence.models import Base


class SqlDatabase:
    def __init__(self, url: str, pooling: bool = True) -> None:
        self._url = url
        options = {} if pooling else {"poolclass": NullPool}
        self._engine = create_async_engine(url, **options)
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @property
    def url(self) -> str:
        return self._url

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    @property
    def dialect_name(self) -> str:
        return self._engine.dialect.name

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session

    async def create_schema(self) -> None:
        async with self._engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self._engine.dispose()

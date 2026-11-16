import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from vortemis.application.errors import NotFoundError
from vortemis.application.queries.dto import OperatorIdentity
from vortemis.infrastructure.persistence.api_tokens import SqlTokenStore
from vortemis.infrastructure.persistence.auth import seed_default_operators
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.models import ApiToken


@pytest.fixture
async def database(tmp_path: Path) -> AsyncIterator[SqlDatabase]:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'tokens.db').as_posix()}",
        pooling=False,
    )
    await database.create_schema()
    async with database.session() as session:
        await seed_default_operators(session)
        await session.commit()
    yield database
    await database.dispose()


def _identity() -> OperatorIdentity:
    return OperatorIdentity(username="admin_carles", role="admin")


async def test_issue_and_resolve(database: SqlDatabase) -> None:
    store = SqlTokenStore(database)
    issued = await store.issue(
        _identity(), datetime.now(UTC) + timedelta(hours=1)
    )

    identity = await store.resolve(issued.token)

    assert identity == _identity()
    assert len(issued.token) >= 40


async def test_token_is_stored_as_a_hash(database: SqlDatabase) -> None:
    store = SqlTokenStore(database)
    issued = await store.issue(
        _identity(), datetime.now(UTC) + timedelta(hours=1)
    )

    async with database.session() as session:
        stored = await session.scalar(select(ApiToken.token_hash))

    assert stored == hashlib.sha256(issued.token.encode("utf-8")).hexdigest()
    assert stored != issued.token


async def test_expired_token_is_rejected(database: SqlDatabase) -> None:
    store = SqlTokenStore(database)
    issued = await store.issue(
        _identity(), datetime.now(UTC) - timedelta(seconds=1)
    )

    assert await store.resolve(issued.token) is None


async def test_revoked_token_is_rejected(database: SqlDatabase) -> None:
    store = SqlTokenStore(database)
    issued = await store.issue(
        _identity(), datetime.now(UTC) + timedelta(hours=1)
    )

    await store.revoke(issued.token)

    assert await store.resolve(issued.token) is None


async def test_unknown_operator_cannot_receive_a_token(
    database: SqlDatabase,
) -> None:
    store = SqlTokenStore(database)

    with pytest.raises(NotFoundError):
        await store.issue(
            OperatorIdentity(username="ghost", role="analyst"),
            datetime.now(UTC) + timedelta(hours=1),
        )

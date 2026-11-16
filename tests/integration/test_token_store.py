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


def _expiry(minutes: int = 15) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=minutes)


async def test_create_session_and_resolve_access(
    database: SqlDatabase,
) -> None:
    store = SqlTokenStore(database)

    session = await store.create_session(
        _identity(), _expiry(), _expiry(60)
    )
    identity = await store.resolve_access(session.access_token)

    assert identity == _identity()
    assert len(session.access_token) >= 40
    assert len(session.refresh_token) >= 40


async def test_tokens_are_stored_as_hashes(database: SqlDatabase) -> None:
    store = SqlTokenStore(database)
    session = await store.create_session(
        _identity(), _expiry(), _expiry(60)
    )

    async with database.session() as session_row:
        row = await session_row.scalar(select(ApiToken))

    assert row is not None
    assert row.token_hash == hashlib.sha256(
        session.access_token.encode("utf-8")
    ).hexdigest()
    assert row.refresh_token_hash == hashlib.sha256(
        session.refresh_token.encode("utf-8")
    ).hexdigest()
    assert session.access_token not in {
        row.token_hash,
        row.refresh_token_hash,
    }


async def test_expired_access_token_is_rejected(
    database: SqlDatabase,
) -> None:
    store = SqlTokenStore(database)
    session = await store.create_session(
        _identity(), datetime.now(UTC) - timedelta(seconds=1), _expiry(60)
    )

    assert await store.resolve_access(session.access_token) is None


async def test_rotation_replaces_both_tokens(database: SqlDatabase) -> None:
    store = SqlTokenStore(database)
    session = await store.create_session(
        _identity(), _expiry(), _expiry(60)
    )

    rotated = await store.rotate(session.refresh_token, _expiry(), _expiry(60))

    assert rotated is not None
    assert rotated.access_token != session.access_token
    assert rotated.refresh_token != session.refresh_token
    assert await store.resolve_access(session.access_token) is None
    assert await store.resolve_access(rotated.access_token) == _identity()


async def test_refresh_reuse_revokes_the_session(
    database: SqlDatabase,
) -> None:
    store = SqlTokenStore(database)
    session = await store.create_session(
        _identity(), _expiry(), _expiry(60)
    )
    rotated = await store.rotate(session.refresh_token, _expiry(), _expiry(60))
    assert rotated is not None

    replay = await store.rotate(session.refresh_token, _expiry(), _expiry(60))

    assert replay is None
    assert await store.resolve_access(rotated.access_token) is None


async def test_expired_refresh_token_is_rejected(
    database: SqlDatabase,
) -> None:
    store = SqlTokenStore(database)
    session = await store.create_session(
        _identity(), _expiry(), datetime.now(UTC) - timedelta(seconds=1)
    )

    rotated = await store.rotate(session.refresh_token, _expiry(), _expiry(60))

    assert rotated is None


async def test_revoked_access_token_is_rejected(
    database: SqlDatabase,
) -> None:
    store = SqlTokenStore(database)
    session = await store.create_session(
        _identity(), _expiry(), _expiry(60)
    )

    await store.revoke(session.access_token)

    assert await store.resolve_access(session.access_token) is None


async def test_unknown_operator_cannot_receive_a_session(
    database: SqlDatabase,
) -> None:
    store = SqlTokenStore(database)

    with pytest.raises(NotFoundError):
        await store.create_session(
            OperatorIdentity(username="ghost", role="analyst"),
            _expiry(),
            _expiry(60),
        )

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update

from vortemis.application.errors import NotFoundError
from vortemis.application.ports.driven.token_store import (
    IssuedSession,
    TokenStorePort,
)
from vortemis.application.queries.dto import OperatorIdentity
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.models import ApiToken, SocOperator

_TOKEN_BYTES = 32


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SqlTokenStore(TokenStorePort):
    def __init__(self, database: SqlDatabase) -> None:
        self._database = database

    async def create_session(
        self,
        operator: OperatorIdentity,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> IssuedSession:
        access = secrets.token_urlsafe(_TOKEN_BYTES)
        refresh = secrets.token_urlsafe(_TOKEN_BYTES)
        async with self._database.session() as session:
            operator_id = await session.scalar(
                select(SocOperator.operator_id).where(
                    SocOperator.username == operator.username
                )
            )
            if operator_id is None:
                raise NotFoundError(f"unknown operator: {operator.username}")
            session.add(
                ApiToken(
                    token_hash=_digest(access),
                    refresh_token_hash=_digest(refresh),
                    operator_id=operator_id,
                    created_at=datetime.now(UTC),
                    expires_at=access_expires_at,
                    refresh_expires_at=refresh_expires_at,
                )
            )
            await session.commit()
        return IssuedSession(
            access_token=access,
            refresh_token=refresh,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    async def resolve_access(self, token: str) -> OperatorIdentity | None:
        async with self._database.session() as session:
            row = (
                await session.execute(
                    select(
                        SocOperator.username,
                        SocOperator.role,
                        ApiToken.expires_at,
                    )
                    .join(
                        ApiToken,
                        ApiToken.operator_id == SocOperator.operator_id,
                    )
                    .where(
                        ApiToken.token_hash == _digest(token),
                        ApiToken.revoked_at.is_(None),
                    )
                )
            ).first()
        if row is None:
            return None
        if _aware(row.expires_at) <= datetime.now(UTC):
            return None
        return OperatorIdentity(username=row.username, role=row.role)

    async def rotate(
        self,
        refresh_token: str,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> IssuedSession | None:
        digest = _digest(refresh_token)
        async with self._database.session() as session:
            row = await session.scalar(
                select(ApiToken).where(
                    ApiToken.refresh_token_hash == digest,
                    ApiToken.revoked_at.is_(None),
                )
            )
            if row is None:
                replay = await session.scalar(
                    select(ApiToken).where(
                        ApiToken.previous_refresh_hash == digest,
                        ApiToken.revoked_at.is_(None),
                    )
                )
                if replay is not None:
                    replay.revoked_at = datetime.now(UTC)
                    await session.commit()
                return None
            if row.refresh_expires_at is None:
                return None
            if _aware(row.refresh_expires_at) <= datetime.now(UTC):
                return None
            access = secrets.token_urlsafe(_TOKEN_BYTES)
            refresh = secrets.token_urlsafe(_TOKEN_BYTES)
            row.previous_refresh_hash = row.refresh_token_hash
            row.refresh_token_hash = _digest(refresh)
            row.token_hash = _digest(access)
            row.expires_at = access_expires_at
            row.refresh_expires_at = refresh_expires_at
            await session.commit()
        return IssuedSession(
            access_token=access,
            refresh_token=refresh,
            access_expires_at=access_expires_at,
            refresh_expires_at=refresh_expires_at,
        )

    async def revoke(self, access_token: str) -> None:
        async with self._database.session() as session:
            await session.execute(
                update(ApiToken)
                .where(
                    ApiToken.token_hash == _digest(access_token),
                    ApiToken.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            )
            await session.commit()

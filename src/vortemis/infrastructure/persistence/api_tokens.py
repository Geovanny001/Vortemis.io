import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update

from vortemis.application.ports.driven.token_store import IssuedToken, TokenStorePort
from vortemis.application.queries.dto import OperatorIdentity
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.models import ApiToken, SocOperator

_TOKEN_BYTES = 32


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SqlTokenStore(TokenStorePort):
    def __init__(self, database: SqlDatabase) -> None:
        self._database = database

    async def issue(
        self, operator: OperatorIdentity, expires_at: datetime
    ) -> IssuedToken:
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        async with self._database.session() as session:
            operator_id = await session.scalar(
                select(SocOperator.operator_id).where(
                    SocOperator.username == operator.username
                )
            )
            if operator_id is None:
                raise ValueError(f"unknown operator: {operator.username}")
            session.add(
                ApiToken(
                    token_hash=_digest(token),
                    operator_id=operator_id,
                    created_at=datetime.now(UTC),
                    expires_at=expires_at,
                )
            )
            await session.commit()
        return IssuedToken(token=token, expires_at=expires_at)

    async def resolve(self, token: str) -> OperatorIdentity | None:
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
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= datetime.now(UTC):
            return None
        return OperatorIdentity(username=row.username, role=row.role)

    async def revoke(self, token: str) -> None:
        async with self._database.session() as session:
            await session.execute(
                update(ApiToken)
                .where(
                    ApiToken.token_hash == _digest(token),
                    ApiToken.revoked_at.is_(None),
                )
                .values(revoked_at=datetime.now(UTC))
            )
            await session.commit()

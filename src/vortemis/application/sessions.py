from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from vortemis.application.ports.driven.operator_auth import OperatorAuthPort
from vortemis.application.ports.driven.token_store import (
    IssuedSession,
    TokenStorePort,
)
from vortemis.application.queries.dto import OperatorIdentity

DEFAULT_ACCESS_TTL = timedelta(minutes=15)
DEFAULT_REFRESH_TTL = timedelta(days=30)


@dataclass(frozen=True, slots=True)
class LoginResult:
    session: IssuedSession
    identity: OperatorIdentity


class OperatorSessionService:
    def __init__(
        self,
        auth: OperatorAuthPort,
        tokens: TokenStorePort,
        access_ttl: timedelta = DEFAULT_ACCESS_TTL,
        refresh_ttl: timedelta = DEFAULT_REFRESH_TTL,
    ) -> None:
        self._auth = auth
        self._tokens = tokens
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    async def login(self, username: str, password: str) -> LoginResult | None:
        identity = await self._auth.authenticate(username, password)
        if identity is None:
            return None
        session = await self._tokens.create_session(
            identity,
            access_expires_at=datetime.now(UTC) + self._access_ttl,
            refresh_expires_at=datetime.now(UTC) + self._refresh_ttl,
        )
        return LoginResult(session=session, identity=identity)

    async def refresh(self, refresh_token: str) -> LoginResult | None:
        session = await self._tokens.rotate(
            refresh_token,
            access_expires_at=datetime.now(UTC) + self._access_ttl,
            refresh_expires_at=datetime.now(UTC) + self._refresh_ttl,
        )
        if session is None:
            return None
        identity = await self._tokens.resolve_access(session.access_token)
        if identity is None:
            return None
        return LoginResult(session=session, identity=identity)

    async def resolve(self, token: str) -> OperatorIdentity | None:
        return await self._tokens.resolve_access(token)

    async def logout(self, token: str) -> None:
        await self._tokens.revoke(token)

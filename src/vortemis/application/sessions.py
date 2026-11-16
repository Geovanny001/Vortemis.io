from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from vortemis.application.ports.driven.operator_auth import OperatorAuthPort
from vortemis.application.ports.driven.token_store import IssuedToken, TokenStorePort
from vortemis.application.queries.dto import OperatorIdentity

DEFAULT_TOKEN_TTL = timedelta(hours=12)


@dataclass(frozen=True, slots=True)
class LoginResult:
    token: IssuedToken
    identity: OperatorIdentity


class OperatorSessionService:
    def __init__(
        self,
        auth: OperatorAuthPort,
        tokens: TokenStorePort,
        ttl: timedelta = DEFAULT_TOKEN_TTL,
    ) -> None:
        self._auth = auth
        self._tokens = tokens
        self._ttl = ttl

    async def login(self, username: str, password: str) -> LoginResult | None:
        identity = await self._auth.authenticate(username, password)
        if identity is None:
            return None
        expires_at = datetime.now(UTC) + self._ttl
        token = await self._tokens.issue(identity, expires_at)
        return LoginResult(token=token, identity=identity)

    async def resolve(self, token: str) -> OperatorIdentity | None:
        return await self._tokens.resolve(token)

    async def logout(self, token: str) -> None:
        await self._tokens.revoke(token)

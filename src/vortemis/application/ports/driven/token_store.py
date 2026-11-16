from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from vortemis.application.queries.dto import OperatorIdentity


@dataclass(frozen=True, slots=True)
class IssuedSession:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime


class TokenStorePort(Protocol):
    async def create_session(
        self,
        operator: OperatorIdentity,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> IssuedSession:
        ...

    async def resolve_access(self, token: str) -> OperatorIdentity | None:
        ...

    async def rotate(
        self,
        refresh_token: str,
        access_expires_at: datetime,
        refresh_expires_at: datetime,
    ) -> IssuedSession | None:
        ...

    async def revoke(self, access_token: str) -> None:
        ...

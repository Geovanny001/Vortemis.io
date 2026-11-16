from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from vortemis.application.queries.dto import OperatorIdentity


@dataclass(frozen=True, slots=True)
class IssuedToken:
    token: str
    expires_at: datetime


class TokenStorePort(Protocol):
    async def issue(
        self, operator: OperatorIdentity, expires_at: datetime
    ) -> IssuedToken:
        ...

    async def resolve(self, token: str) -> OperatorIdentity | None:
        ...

    async def revoke(self, token: str) -> None:
        ...

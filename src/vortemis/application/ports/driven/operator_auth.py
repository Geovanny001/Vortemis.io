from typing import Protocol

from vortemis.application.queries.dto import OperatorIdentity


class OperatorAuthPort(Protocol):
    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> OperatorIdentity | None:
        ...

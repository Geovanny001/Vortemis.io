from vortemis.application.ports.driven.operator_auth import OperatorAuthPort
from vortemis.application.queries.dto import OperatorIdentity
from vortemis.infrastructure.persistence.auth import authenticate_operator
from vortemis.infrastructure.persistence.session import session_scope


class SqlOperatorAuth(OperatorAuthPort):
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> OperatorIdentity | None:
        async with session_scope(self._database_url) as session:
            operator = await authenticate_operator(session, username, password)
            if operator is None:
                return None
            return OperatorIdentity(username=operator.username, role=operator.role)

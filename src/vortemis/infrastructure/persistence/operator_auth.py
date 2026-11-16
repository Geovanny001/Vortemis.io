from vortemis.application.ports.driven.operator_auth import OperatorAuthPort
from vortemis.application.queries.dto import OperatorIdentity
from vortemis.infrastructure.persistence.auth import authenticate_operator
from vortemis.infrastructure.persistence.database import SqlDatabase


class SqlOperatorAuth(OperatorAuthPort):
    def __init__(self, database: SqlDatabase) -> None:
        self._database = database

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> OperatorIdentity | None:
        async with self._database.session() as session:
            operator = await authenticate_operator(session, username, password)
            if operator is None:
                return None
            return OperatorIdentity(username=operator.username, role=operator.role)

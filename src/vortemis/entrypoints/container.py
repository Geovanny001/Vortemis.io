from datetime import timedelta
from pathlib import Path

from vortemis.application.queries.telemetry import TelemetryReadService
from vortemis.application.sessions import OperatorSessionService
from vortemis.infrastructure.model.metadata import TorchEngineMetadata
from vortemis.infrastructure.persistence.api_tokens import SqlTokenStore
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.flow_query import SqlFlowQuery
from vortemis.infrastructure.persistence.operator_admin import SqlOperatorAdmin
from vortemis.infrastructure.persistence.operator_auth import SqlOperatorAuth
from vortemis.infrastructure.persistence.telemetry_maintenance import (
    DatabaseTelemetryMaintenance,
)


def build_telemetry_service(
    database: SqlDatabase, model_path: Path
) -> TelemetryReadService:
    return TelemetryReadService(
        flow_query=SqlFlowQuery(database),
        auth=SqlOperatorAuth(database),
        maintenance=DatabaseTelemetryMaintenance(database),
        metadata=TorchEngineMetadata(model_path),
    )


def build_session_service(
    database: SqlDatabase,
    access_ttl: timedelta,
    refresh_ttl: timedelta,
) -> OperatorSessionService:
    return OperatorSessionService(
        auth=SqlOperatorAuth(database),
        tokens=SqlTokenStore(database),
        access_ttl=access_ttl,
        refresh_ttl=refresh_ttl,
    )


def build_operator_admin(database: SqlDatabase) -> SqlOperatorAdmin:
    return SqlOperatorAdmin(database)

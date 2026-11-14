from vortemis.application.queries.telemetry import TelemetryReadService
from vortemis.infrastructure.persistence.flow_query import SqlFlowQuery
from vortemis.infrastructure.persistence.operator_auth import SqlOperatorAuth
from vortemis.infrastructure.persistence.telemetry_maintenance import (
    DatabaseTelemetryMaintenance,
)


def build_telemetry_service(database_url: str) -> TelemetryReadService:
    return TelemetryReadService(
        flow_query=SqlFlowQuery(database_url),
        auth=SqlOperatorAuth(database_url),
        maintenance=DatabaseTelemetryMaintenance(database_url),
    )

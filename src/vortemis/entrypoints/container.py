from pathlib import Path

from vortemis.application.queries.telemetry import TelemetryReadService
from vortemis.infrastructure.model.metadata import TorchEngineMetadata
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.flow_query import SqlFlowQuery
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

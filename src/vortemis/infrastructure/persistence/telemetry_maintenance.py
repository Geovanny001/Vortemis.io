from pathlib import Path

from vortemis.application.ports.driven.telemetry_maintenance import (
    TelemetryMaintenancePort,
)
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.maintenance import purge_telemetry


class DatabaseTelemetryMaintenance(TelemetryMaintenancePort):
    def __init__(self, database: SqlDatabase) -> None:
        self._database = database

    async def purge(self, log_file: Path) -> None:
        await purge_telemetry(self._database, log_file)

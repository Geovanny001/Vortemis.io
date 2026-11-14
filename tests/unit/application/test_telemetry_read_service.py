from datetime import UTC, datetime
from pathlib import Path

from vortemis.application.queries.dto import FlowRecord, OperatorIdentity
from vortemis.application.queries.telemetry import TelemetryReadService

_RECORD = FlowRecord(
    ts=datetime(2026, 11, 14, tzinfo=UTC),
    flow_id="flow-1",
    src_ip="192.168.1.10",
    dst_ip="10.0.0.5",
    src_port=50000,
    dst_port=445,
    protocol="tcp",
    conn_state="SF",
    iat_ms=10.0,
    orig_bytes=1000,
    resp_bytes=200,
    duration=0.5,
    anomaly_probability=0.91,
    is_anomaly=True,
    mitre_tactic="TA0008",
)


class FakeFlowQuery:
    def __init__(self) -> None:
        self.load_limit: int | None = None
        self.threshold: float | None = None

    async def load_flows(self, limit: int) -> list[FlowRecord]:
        self.load_limit = limit
        return [_RECORD]

    async def count_flows(self) -> int:
        return 3

    async def count_anomalies(self, threshold: float) -> int:
        self.threshold = threshold
        return 2

    async def count_by_tactic(self) -> dict[str, int]:
        return {"TA0008": 1}


class FakeAuth:
    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> OperatorIdentity | None:
        if username == "admin" and password == "secret":
            return OperatorIdentity(username="admin", role="admin")
        return None


class FakeMaintenance:
    def __init__(self) -> None:
        self.purged: Path | None = None

    async def purge(self, log_file: Path) -> None:
        self.purged = log_file


async def test_service_delegates_flow_queries() -> None:
    flow_query = FakeFlowQuery()
    service = TelemetryReadService(
        flow_query=flow_query,
        auth=FakeAuth(),
        maintenance=FakeMaintenance(),
    )

    records = await service.load_flows(limit=25)

    assert records == [_RECORD]
    assert flow_query.load_limit == 25
    assert await service.count_flows() == 3
    assert await service.count_anomalies(0.7) == 2
    assert flow_query.threshold == 0.7
    assert await service.count_by_tactic() == {"TA0008": 1}


async def test_service_delegates_auth_and_purge(tmp_path: Path) -> None:
    maintenance = FakeMaintenance()
    service = TelemetryReadService(
        flow_query=FakeFlowQuery(),
        auth=FakeAuth(),
        maintenance=maintenance,
    )

    identity = await service.authenticate("admin", "secret")
    rejected = await service.authenticate("admin", "wrong")
    log_file = tmp_path / "conn.log"
    await service.purge(log_file)

    assert identity == OperatorIdentity(username="admin", role="admin")
    assert rejected is None
    assert maintenance.purged == log_file

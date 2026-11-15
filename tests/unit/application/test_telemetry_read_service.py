from datetime import UTC, datetime
from pathlib import Path

from vortemis.application.queries.dto import (
    FlowPage,
    FlowRecord,
    OperatorIdentity,
    SourceAggregate,
    TimelinePoint,
)
from vortemis.application.queries.filters import FlowFilters
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
        self.search: tuple[FlowFilters | None, int, str | None] | None = None
        self.count_filters: FlowFilters | None = None
        self.anomaly_call: tuple[float, FlowFilters | None] | None = None
        self.tactic_filters: FlowFilters | None = None
        self.sources: tuple[float, FlowFilters | None, int] | None = None
        self.timeline_call: tuple[float, int, FlowFilters | None] | None = None

    async def search_flows(
        self,
        filters: FlowFilters | None = None,
        limit: int = 500,
        cursor: str | None = None,
    ) -> FlowPage:
        self.search = (filters, limit, cursor)
        return FlowPage(records=[_RECORD], next_cursor="next-page")

    async def count_flows(self, filters: FlowFilters | None = None) -> int:
        self.count_filters = filters
        return 3

    async def count_anomalies(
        self, threshold: float, filters: FlowFilters | None = None
    ) -> int:
        self.anomaly_call = (threshold, filters)
        return 2

    async def count_by_tactic(
        self, filters: FlowFilters | None = None
    ) -> dict[str, int]:
        self.tactic_filters = filters
        return {"TA0008": 1}

    async def top_sources(
        self,
        threshold: float,
        filters: FlowFilters | None = None,
        limit: int = 10,
    ) -> list[SourceAggregate]:
        self.sources = (threshold, filters, limit)
        return [SourceAggregate(src_ip="192.168.1.10", flows=2, anomalies=1)]

    async def timeline(
        self,
        threshold: float,
        bucket_seconds: int = 60,
        filters: FlowFilters | None = None,
    ) -> list[TimelinePoint]:
        self.timeline_call = (threshold, bucket_seconds, filters)
        return [
            TimelinePoint(
                bucket_start=datetime(2026, 11, 14, tzinfo=UTC),
                flows=2,
                anomalies=1,
            )
        ]


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


def _service(flow_query: FakeFlowQuery) -> TelemetryReadService:
    return TelemetryReadService(
        flow_query=flow_query,
        auth=FakeAuth(),
        maintenance=FakeMaintenance(),
    )


async def test_service_delegates_flow_queries() -> None:
    flow_query = FakeFlowQuery()
    service = _service(flow_query)
    filters = FlowFilters(src_ip="192.168.1.10", min_probability=0.7)

    page = await service.search_flows(filters=filters, limit=25, cursor="abc")

    assert page.records == [_RECORD]
    assert page.next_cursor == "next-page"
    assert flow_query.search == (filters, 25, "abc")
    assert await service.count_flows(filters) == 3
    assert flow_query.count_filters == filters
    assert await service.count_anomalies(0.7, filters) == 2
    assert flow_query.anomaly_call == (0.7, filters)
    assert await service.count_by_tactic(filters) == {"TA0008": 1}
    assert flow_query.tactic_filters == filters
    assert await service.top_sources(0.7, filters, limit=5) == [
        SourceAggregate(src_ip="192.168.1.10", flows=2, anomalies=1)
    ]
    assert flow_query.sources == (0.7, filters, 5)
    assert len(await service.timeline(0.7, bucket_seconds=300, filters=filters)) == 1
    assert flow_query.timeline_call == (0.7, 300, filters)


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

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from vortemis.application.queries.filters import FlowFilters
from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp
from vortemis.infrastructure.persistence.auth import seed_default_operators
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.flow_query import SqlFlowQuery
from vortemis.infrastructure.persistence.operator_auth import SqlOperatorAuth
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)

_BASE_EPOCH = 1_700_000_000.0


def _flow(
    offset: float,
    probability: float,
    tactic: str | None,
    src_ip: str = "192.168.1.10",
    dst_port: int = 445,
    proto: str = "tcp",
) -> NetworkFlow:
    return NetworkFlow(
        src_ip=IPAddress(src_ip),
        dst_ip=IPAddress("10.0.0.5"),
        src_port=Port(50000),
        dst_port=Port(dst_port),
        proto=Protocol.from_raw(proto),
        ts=Timestamp.from_epoch(_BASE_EPOCH + offset),
        orig_bytes=1000,
        resp_bytes=200,
        duration=0.5,
        conn_state="SF",
        anomaly_probability=probability,
        mitre_tactic=tactic,
    )


@pytest.fixture
async def database(tmp_path: Path) -> AsyncIterator[SqlDatabase]:
    database = SqlDatabase(
        f"sqlite+aiosqlite:///{(tmp_path / 'query.db').as_posix()}",
        pooling=False,
    )
    await database.create_schema()
    repository = PostgresFlowRepository(database.session_factory)
    await repository.save_batch(
        [
            _flow(0, 0.10, None, "192.168.1.10", 445, "tcp"),
            _flow(100, 0.90, "TA0043", "192.168.1.11", 53, "udp"),
            _flow(200, 0.80, "TA0010", "192.168.1.12", 443, "tcp"),
            _flow(300, 0.95, "TA0008", "192.168.1.10", 22, "tcp"),
            _flow(400, 0.05, None, "192.168.1.13", 8080, "tcp"),
        ]
    )
    async with database.session() as session:
        await seed_default_operators(session)
        await session.commit()
    yield database
    await database.dispose()


@pytest.fixture
def query(database: SqlDatabase) -> SqlFlowQuery:
    return SqlFlowQuery(database)


async def test_search_returns_dtos_in_descending_order(
    query: SqlFlowQuery,
) -> None:
    page = await query.search_flows(limit=10)

    assert [record.dst_port for record in page.records] == [8080, 22, 443, 53, 445]
    assert page.records[0].protocol == "tcp"
    assert page.records[1].conn_state == "SF"
    assert page.next_cursor is None


async def test_search_paginates_with_a_cursor(query: SqlFlowQuery) -> None:
    first = await query.search_flows(limit=2)
    second = await query.search_flows(limit=2, cursor=first.next_cursor)
    third = await query.search_flows(limit=2, cursor=second.next_cursor)

    assert [record.dst_port for record in first.records] == [8080, 22]
    assert [record.dst_port for record in second.records] == [443, 53]
    assert [record.dst_port for record in third.records] == [445]
    assert second.next_cursor is not None
    assert third.next_cursor is None


async def test_search_applies_filters(query: SqlFlowQuery) -> None:
    by_source = await query.search_flows(
        filters=FlowFilters(src_ip="192.168.1.10")
    )
    by_protocol = await query.search_flows(filters=FlowFilters(protocol="UDP"))
    by_tactic = await query.search_flows(filters=FlowFilters(tactic="ta0010"))
    by_port = await query.search_flows(filters=FlowFilters(dst_port=22))
    by_probability = await query.search_flows(
        filters=FlowFilters(min_probability=0.8)
    )
    by_window = await query.search_flows(
        filters=FlowFilters(
            since=datetime.fromtimestamp(_BASE_EPOCH + 150, tz=UTC),
            until=datetime.fromtimestamp(_BASE_EPOCH + 250, tz=UTC),
        )
    )

    assert [record.dst_port for record in by_source.records] == [22, 445]
    assert [record.dst_port for record in by_protocol.records] == [53]
    assert [record.dst_port for record in by_tactic.records] == [443]
    assert [record.dst_port for record in by_port.records] == [22]
    assert [record.dst_port for record in by_probability.records] == [22, 443, 53]
    assert [record.dst_port for record in by_window.records] == [443]


async def test_counts_respect_filters(query: SqlFlowQuery) -> None:
    assert await query.count_flows() == 5
    assert await query.count_flows(FlowFilters(src_ip="192.168.1.10")) == 2
    assert await query.count_anomalies(0.7) == 3
    assert await query.count_anomalies(0.7, FlowFilters(protocol="tcp")) == 2
    assert await query.count_by_tactic() == {
        "TA0008": 1,
        "TA0010": 1,
        "TA0043": 1,
    }
    assert await query.count_by_tactic(FlowFilters(src_ip="192.168.1.10")) == {
        "TA0008": 1
    }


async def test_top_sources_orders_by_volume(query: SqlFlowQuery) -> None:
    sources = await query.top_sources(0.7, limit=2)

    assert len(sources) == 2
    assert sources[0].src_ip == "192.168.1.10"
    assert sources[0].flows == 2
    assert sources[0].anomalies == 1

    all_sources = await query.top_sources(0.7, limit=10)
    by_ip = {source.src_ip: source for source in all_sources}

    assert by_ip["192.168.1.11"].anomalies == 1
    assert by_ip["192.168.1.13"].anomalies == 0


async def test_timeline_buckets_by_window(query: SqlFlowQuery) -> None:
    points = await query.timeline(0.7, bucket_seconds=600)
    narrow = await query.timeline(0.7, bucket_seconds=60)

    assert [point.flows for point in points] == [4, 1]
    assert [point.anomalies for point in points] == [3, 0]
    assert sum(point.flows for point in points) == 5
    assert len(narrow) == 5


async def test_invalid_cursor_and_arguments_are_rejected(
    query: SqlFlowQuery,
) -> None:
    with pytest.raises(ValueError):
        await query.search_flows(cursor="not-a-cursor")
    with pytest.raises(ValueError):
        await query.search_flows(limit=0)
    with pytest.raises(ValueError):
        await query.count_anomalies(1.5)
    with pytest.raises(ValueError):
        await query.timeline(0.7, bucket_seconds=0)


async def test_operator_authentication_still_works(
    database: SqlDatabase,
) -> None:
    auth = SqlOperatorAuth(database)
    identity = await auth.authenticate("admin_carles", "VortemisAdmin2026!")

    assert identity is not None
    assert identity.role == "admin"

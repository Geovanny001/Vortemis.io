from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp
from vortemis.infrastructure.persistence.models import (
    Base,
    DimConnState,
    DimMitreTactic,
    DimProtocol,
    FactNetworkFlow,
)
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)


@pytest.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _flow(
    src: str,
    dst: str,
    proto: str,
    conn_state: str | None,
    orig_bytes: int = 100,
    iat_ms: float | None = 10.0,
    anomaly_probability: float = 0.0,
    mitre_tactic: str | None = None,
) -> NetworkFlow:
    return NetworkFlow(
        src_ip=IPAddress(src),
        dst_ip=IPAddress(dst),
        src_port=Port(12345),
        dst_port=Port(443),
        proto=Protocol.from_raw(proto),
        ts=Timestamp.from_epoch(1_700_000_000.0),
        orig_bytes=orig_bytes,
        resp_bytes=200,
        duration=1.5,
        iat_ms=iat_ms,
        conn_state=conn_state,
        anomaly_probability=anomaly_probability,
        mitre_tactic=mitre_tactic,
    )


async def test_save_batch_persists_flows_and_dimensions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = PostgresFlowRepository(session_factory)

    await repository.save_batch(
        [
            _flow("10.0.0.1", "10.0.0.2", "tcp", "SF"),
            _flow("10.0.0.3", "10.0.0.4", "udp", None),
        ]
    )

    async with session_factory() as session:
        fact_count = await session.scalar(
            select(func.count()).select_from(FactNetworkFlow)
        )
        protocol_count = await session.scalar(
            select(func.count()).select_from(DimProtocol)
        )
        conn_state_count = await session.scalar(
            select(func.count()).select_from(DimConnState)
        )

    assert fact_count == 2
    assert protocol_count == 2
    assert conn_state_count == 1


async def test_save_batch_reuses_existing_dimension_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = PostgresFlowRepository(session_factory)

    await repository.save_batch([_flow("10.0.0.1", "10.0.0.2", "tcp", "SF")])
    await repository.save_batch([_flow("10.0.0.5", "10.0.0.6", "tcp", "SF")])

    async with session_factory() as session:
        fact_count = await session.scalar(
            select(func.count()).select_from(FactNetworkFlow)
        )
        protocol_count = await session.scalar(
            select(func.count()).select_from(DimProtocol)
        )
        conn_state_count = await session.scalar(
            select(func.count()).select_from(DimConnState)
        )

    assert fact_count == 2
    assert protocol_count == 1
    assert conn_state_count == 1


async def test_save_batch_persists_anomaly_probability_and_tactic(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = PostgresFlowRepository(session_factory)

    await repository.save_batch(
        [
            _flow(
                "10.0.0.1",
                "10.0.0.2",
                "tcp",
                "SF",
                anomaly_probability=0.92,
                mitre_tactic="TA0010",
            )
        ]
    )

    async with session_factory() as session:
        row = await session.scalar(select(FactNetworkFlow))
        tactic = await session.scalar(
            select(DimMitreTactic).where(
                DimMitreTactic.tactic_id == row.tactic_id
            )
        )

    assert row is not None
    assert row.anomaly_probability == 0.92
    assert row.is_anomaly is True
    assert row.tactic_id is not None
    assert tactic is not None
    assert tactic.mitre_id == "TA0010"


async def test_save_batch_normal_flow_has_no_tactic(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    repository = PostgresFlowRepository(session_factory)

    await repository.save_batch(
        [_flow("10.0.0.1", "10.0.0.2", "tcp", "SF", anomaly_probability=0.05)]
    )

    async with session_factory() as session:
        row = await session.scalar(select(FactNetworkFlow))

    assert row is not None
    assert row.is_anomaly is False
    assert row.tactic_id is None

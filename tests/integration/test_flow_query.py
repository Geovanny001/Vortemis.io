from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp
from vortemis.infrastructure.persistence.auth import seed_default_operators
from vortemis.infrastructure.persistence.flow_query import SqlFlowQuery
from vortemis.infrastructure.persistence.models import Base
from vortemis.infrastructure.persistence.operator_auth import SqlOperatorAuth
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)


def _flow(
    epoch: float,
    probability: float,
    tactic: str | None,
    src_ip: str = "192.168.1.10",
    dst_port: int = 445,
) -> NetworkFlow:
    return NetworkFlow(
        src_ip=IPAddress(src_ip),
        dst_ip=IPAddress("10.0.0.5"),
        src_port=Port(50000),
        dst_port=Port(dst_port),
        proto=Protocol.TCP,
        ts=Timestamp.from_epoch(epoch),
        orig_bytes=1000,
        resp_bytes=200,
        duration=0.5,
        conn_state="SF",
        anomaly_probability=probability,
        mitre_tactic=tactic,
    )


async def test_sql_flow_query_returns_dtos_and_counts(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'query.db').as_posix()}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = PostgresFlowRepository(session_factory)
    await repository.save_batch(
        [
            _flow(1_700_000_000.0, 0.10, None),
            _flow(1_700_000_100.0, 0.90, "TA0043", src_ip="192.168.1.11"),
            _flow(1_700_000_200.0, 0.80, "TA0010", src_ip="192.168.1.12"),
        ]
    )
    async with session_factory() as session:
        await seed_default_operators(session)
        await session.commit()
    await engine.dispose()

    query = SqlFlowQuery(database_url)
    records = await query.load_flows(limit=10)

    assert [record.mitre_tactic for record in records] == ["TA0010", "TA0043", None]
    assert records[0].src_ip == "192.168.1.12"
    assert records[0].protocol == "tcp"
    assert records[0].conn_state == "SF"
    assert await query.count_flows() == 3
    assert await query.count_anomalies(0.7) == 2
    assert await query.count_by_tactic() == {"TA0010": 1, "TA0043": 1}

    auth = SqlOperatorAuth(database_url)
    identity = await auth.authenticate("admin_carles", "VortemisAdmin2026!")

    assert identity is not None
    assert identity.role == "admin"

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp
from vortemis.infrastructure.persistence.maintenance import purge_telemetry
from vortemis.infrastructure.persistence.models import (
    Base,
    FactNetworkFlow,
    IngestionState,
)
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)
from vortemis.infrastructure.zeek.header import ZEEK_CONN_HEADER


def _flow() -> NetworkFlow:
    return NetworkFlow(
        src_ip=IPAddress("10.0.0.1"),
        dst_ip=IPAddress("10.0.0.2"),
        src_port=Port(12345),
        dst_port=Port(443),
        proto=Protocol.TCP,
        ts=Timestamp.from_epoch(1_700_000_000.0),
        orig_bytes=100,
        resp_bytes=200,
        duration=1.0,
        conn_state="SF",
    )


async def test_purge_telemetry_removes_flows_and_rewrites_log(tmp_path: Path) -> None:
    db_path = tmp_path / "vortemis.db"
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repository = PostgresFlowRepository(session_factory)
    await repository.save_batch([_flow()])
    async with session_factory() as session:
        session.add(
            IngestionState(
                source_path=str(tmp_path / "conn.log"),
                device=0,
                inode=0,
                offset=42,
                updated_at=datetime.now(UTC),
            )
        )
        await session.commit()
    await engine.dispose()

    log_file = tmp_path / "conn.log"
    log_file.write_text("\n".join(ZEEK_CONN_HEADER) + "\nrow\n", encoding="utf-8")

    await purge_telemetry(database_url, log_file)

    engine = create_async_engine(database_url)
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        count = await session.scalar(select(func.count()).select_from(FactNetworkFlow))
        states = await session.scalar(
            select(func.count()).select_from(IngestionState)
        )
    await engine.dispose()

    assert count == 0
    assert states == 0
    assert log_file.read_text(encoding="utf-8") == "\n".join(ZEEK_CONN_HEADER) + "\n"

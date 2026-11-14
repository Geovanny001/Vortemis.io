from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from streamlit.testing.v1 import AppTest

from vortemis.domain.entities.network_flow import NetworkFlow
from vortemis.domain.value_objects.ip_address import IPAddress
from vortemis.domain.value_objects.port import Port
from vortemis.domain.value_objects.protocol import Protocol
from vortemis.domain.value_objects.timestamp import Timestamp
from vortemis.infrastructure.persistence.models import Base
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)
from vortemis.infrastructure.zeek.header import ZEEK_CONN_HEADER

_DASHBOARD_PATH = str(Path("src/vortemis/entrypoints/dashboard.py").resolve())
_MODEL_PATH = str(Path("models/vortemis_ae.pt").resolve())


def _flow() -> NetworkFlow:
    return NetworkFlow(
        src_ip=IPAddress("192.168.1.10"),
        dst_ip=IPAddress("10.0.0.5"),
        src_port=Port(50000),
        dst_port=Port(445),
        proto=Protocol.TCP,
        ts=Timestamp.from_epoch(1_700_000_000.0),
        orig_bytes=1000,
        resp_bytes=200,
        duration=0.5,
        conn_state="SF",
        anomaly_probability=0.91,
        mitre_tactic="TA0008",
    )


async def test_dashboard_renders_with_data(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "dashboard.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    await PostgresFlowRepository(session_factory).save_batch([_flow()])
    await engine.dispose()

    log_file = tmp_path / "conn.log"
    log_file.write_text("\n".join(ZEEK_CONN_HEADER) + "\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("LOG_FILE", str(log_file))
    monkeypatch.setenv("MODEL_PATH", _MODEL_PATH)

    app = AppTest.from_file(
        _DASHBOARD_PATH,
        default_timeout=30,
    )
    app.session_state["operator"] = "admin_carles"
    app.session_state["role"] = "admin"
    app.session_state["username"] = "admin_carles"

    app.run()

    assert not app.exception


async def test_dashboard_shows_empty_state(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "empty.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()

    log_file = tmp_path / "conn.log"
    log_file.write_text("\n".join(ZEEK_CONN_HEADER) + "\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("LOG_FILE", str(log_file))
    monkeypatch.setenv("MODEL_PATH", _MODEL_PATH)

    app = AppTest.from_file(
        _DASHBOARD_PATH,
        default_timeout=30,
    )
    app.session_state["operator"] = "admin_carles"
    app.session_state["role"] = "admin"
    app.session_state["username"] = "admin_carles"

    app.run()

    assert not app.exception
    assert any("No telemetry yet" in block.value for block in app.markdown)

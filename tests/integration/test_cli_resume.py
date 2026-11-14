from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.entrypoints import cli
from vortemis.infrastructure.persistence.models import FactNetworkFlow, IngestionState

_HEADER = (
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p"
    "\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state\n"
)
_ROWS = [
    "1700000000.000000\tC1\t192.168.1.10\t50000\t8.8.8.8\t53\tudp\tdns\t0.001\t50\t60\tSF",
    "1700000000.100000\tC2\t192.168.1.10\t50001\t8.8.8.8\t53\tudp\tdns\t0.001\t50\t60\tSF",
    "1700000000.200000\tC3\t192.168.1.11\t50002\t1.1.1.1\t443\ttcp\tssl\t0.5\t500\t1000\tSF",
]
_ROW_4 = (
    "1700000000.300000\tC4\t192.168.1.12\t50003\t10.0.0.5\t445"
    "\ttcp\t-\t0.2\t700\t900\tSF"
)
_ROW_5 = (
    "1700000000.400000\tC5\t192.168.1.13\t50004\t10.0.0.6\t22"
    "\ttcp\tssh\t1.0\t900\t1200\tSF"
)
_MODEL_PATH = Path("models/vortemis_ae.pt").resolve()


async def _count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            value = await session.scalar(
                select(func.count()).select_from(FactNetworkFlow)
            )
        return int(value or 0)
    finally:
        await engine.dispose()


async def _offset(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            value = await session.scalar(select(IngestionState.offset))
        return int(value or 0)
    finally:
        await engine.dispose()


def _configure(monkeypatch, log_path: Path, database_url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("LOG_FILE", str(log_path))
    monkeypatch.setenv("MODEL_PATH", str(_MODEL_PATH))
    monkeypatch.setenv("CONTINUOUS_MODE", "false")


async def test_cli_resumes_from_the_persisted_offset(
    tmp_path: Path, monkeypatch
) -> None:
    log_path = tmp_path / "conn.log"
    log_path.write_text(_HEADER + "\n".join(_ROWS) + "\n")
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'vortemis.db').as_posix()}"
    _configure(monkeypatch, log_path, database_url)

    await cli.main()

    assert await _count(database_url) == len(_ROWS)
    assert await _offset(database_url) == log_path.stat().st_size

    with log_path.open("a") as handle:
        handle.write(_ROW_4 + "\n")

    await cli.main()

    assert await _count(database_url) == len(_ROWS) + 1
    assert await _offset(database_url) == log_path.stat().st_size


async def test_cli_reprocesses_the_log_after_truncation(
    tmp_path: Path, monkeypatch
) -> None:
    log_path = tmp_path / "conn.log"
    log_path.write_text(_HEADER + "\n".join(_ROWS) + "\n")
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'vortemis.db').as_posix()}"
    _configure(monkeypatch, log_path, database_url)

    await cli.main()

    assert await _count(database_url) == len(_ROWS)

    log_path.write_text(_HEADER + _ROW_5 + "\n")

    await cli.main()

    assert await _count(database_url) == len(_ROWS) + 1
    assert await _offset(database_url) == log_path.stat().st_size

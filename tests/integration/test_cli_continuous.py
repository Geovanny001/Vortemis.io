import asyncio
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.entrypoints import cli
from vortemis.infrastructure.persistence.models import FactNetworkFlow

_HEADER = (
    "#fields\tts\tuid\tid.orig_h\tid.orig_p\tid.resp_h\tid.resp_p"
    "\tproto\tservice\tduration\torig_bytes\tresp_bytes\tconn_state\n"
)
_ROWS = [
    "1700000000.000000\tC1\t192.168.1.10\t50000\t8.8.8.8\t53\tudp\tdns\t0.001\t50\t60\tSF",
    "1700000000.100000\tC2\t192.168.1.10\t50001\t8.8.8.8\t53\tudp\tdns\t0.001\t50\t60\tSF",
    "1700000000.200000\tC3\t192.168.1.11\t50002\t1.1.1.1\t443\ttcp\tssl\t0.5\t500\t1000\tSF",
    "1700000000.300000\tC4\t192.168.1.11\t50003\t1.1.1.1\t443\ttcp\tssl\t0.5\t500\t1000\tSF",
    "1700000000.400000\tC5\t192.168.1.12\t50004\t10.0.0.5\t22\ttcp\tssh\t2.0\t3000\t4000\tSF",
]
_ROW_6 = (
    "1700000000.500000\tC6\t192.168.1.13\t50005\t10.0.0.6\t445"
    "\ttcp\t-\t0.2\t700\t900\tSF"
)
_MODEL_PATH = Path("models/vortemis_ae.pt").resolve()


async def _count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    try:
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as session:
            value = await session.scalar(
                select(func.count()).select_from(FactNetworkFlow)
            )
        return int(value or 0)
    finally:
        await engine.dispose()


async def _wait_for_rows(database_url: str, expected: int, max_wait: float) -> int:
    deadline = asyncio.get_running_loop().time() + max_wait
    count = 0
    while asyncio.get_running_loop().time() < deadline:
        try:
            count = await _count(database_url)
        except Exception:
            count = 0
        if count >= expected:
            return count
        await asyncio.sleep(0.1)
    return count


async def test_continuous_mode_does_not_reingest_existing_rows(
    tmp_path: Path, monkeypatch
) -> None:
    log_path = tmp_path / "conn.log"
    log_path.write_text(_HEADER + "\n".join(_ROWS) + "\n")
    database_path = tmp_path / "vortemis.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("LOG_FILE", str(log_path))
    monkeypatch.setenv("MODEL_PATH", str(_MODEL_PATH))
    monkeypatch.setenv("CONTINUOUS_MODE", "true")

    task = asyncio.create_task(cli.main())
    try:
        initial_count = await _wait_for_rows(database_url, len(_ROWS), max_wait=10.0)
        assert initial_count == len(_ROWS)
        with log_path.open("a") as handle:
            handle.write(_ROW_6 + "\n")
        final_count = await _wait_for_rows(
            database_url, len(_ROWS) + 1, max_wait=10.0
        )
    finally:
        task.cancel()
        outcome = (await asyncio.gather(task, return_exceptions=True))[0]
        if isinstance(outcome, BaseException) and not isinstance(
            outcome, asyncio.CancelledError
        ):
            raise outcome

    assert final_count == len(_ROWS) + 1

import asyncio
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from vortemis.infrastructure.zeek.header import ZEEK_CONN_HEADER


def _rewrite_log(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("\n".join(ZEEK_CONN_HEADER) + "\n", encoding="utf-8")


async def purge_telemetry(database_url: str, log_file: Path) -> None:
    engine = create_async_engine(database_url)
    try:
        statement = (
            "TRUNCATE TABLE fact_network_flows RESTART IDENTITY"
            if engine.dialect.name == "postgresql"
            else "DELETE FROM fact_network_flows"
        )
        async with engine.begin() as connection:
            await connection.execute(text(statement))
            await connection.execute(text("DELETE FROM ingestion_state"))
        await asyncio.to_thread(_rewrite_log, log_file)
    finally:
        await engine.dispose()

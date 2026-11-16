import asyncio
from pathlib import Path

from sqlalchemy import text

from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.zeek.header import ZEEK_CONN_HEADER


def _rewrite_log(log_file: Path) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text("\n".join(ZEEK_CONN_HEADER) + "\n", encoding="utf-8")


async def purge_telemetry(database: SqlDatabase, log_file: Path) -> None:
    statement = (
        "TRUNCATE TABLE fact_network_flows RESTART IDENTITY"
        if database.dialect_name == "postgresql"
        else "DELETE FROM fact_network_flows"
    )
    async with database.session() as session:
        await session.execute(text(statement))
        await session.execute(text("DELETE FROM ingestion_state"))
        await session.commit()
    await asyncio.to_thread(_rewrite_log, log_file)

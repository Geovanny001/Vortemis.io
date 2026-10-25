import asyncio
import os
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.application.use_cases.flow_normalizer import FlowNormalizerUseCase
from vortemis.infrastructure.persistence.models import Base
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)
from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource

BANNER = (
    "#   #  ###  ####  ##### ##### #   # ##### #####       #####  ###   ###\n"
    "#   # #   # #   #   #   #     ## ##   #   #           #     #   # #   #\n"
    "#   # #   # ####    #   ####  # # #   #   ####        ####  #   # #\n"
    " # #  #   # #  #    #   #     #   #   #       #           # #   # #   #\n"
    "  #    ###  #   #   #   ##### #   # ##### #####       #####  ###   ###"
)

CREDITS = "Lead Developer: CRivera Marroquín, Carles Geovanny | Contributors: The Vortemis Team"

DATABASE_URL_ENV = "DATABASE_URL"
DEFAULT_DATABASE_URL = "postgresql+asyncpg://vortemis:vortemis@localhost:5432/vortemis"
LOG_FILE_ENV = "LOG_FILE"
DEFAULT_LOG_FILE = "conn.log"


def print_banner() -> None:
    print(BANNER)
    print(CREDITS)


async def main() -> None:
    print_banner()
    database_url = os.getenv(DATABASE_URL_ENV, DEFAULT_DATABASE_URL)
    log_file = Path(os.getenv(LOG_FILE_ENV, DEFAULT_LOG_FILE))
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    source = ZeekTelemetrySource(log_file)
    repository = PostgresFlowRepository(session_factory)
    use_case = FlowNormalizerUseCase(source=source, repository=repository)
    await use_case.execute()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

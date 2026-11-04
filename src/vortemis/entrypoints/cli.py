import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.application.use_cases.bayesian_pytorch_engine import BayesianPyTorchEngine
from vortemis.application.use_cases.flow_normalizer import FlowNormalizerUseCase
from vortemis.banner import print_banner
from vortemis.config import Settings
from vortemis.infrastructure.persistence.models import Base
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)
from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource


def _load_engine(settings: Settings) -> BayesianPyTorchEngine | None:
    if not settings.model_path.exists():
        return None
    return BayesianPyTorchEngine(settings.model_path, epsilon=settings.epsilon)


async def main() -> None:
    print_banner()
    settings = Settings.from_env()
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    source = ZeekTelemetrySource(settings.log_file)
    repository = PostgresFlowRepository(session_factory, epsilon=settings.epsilon)
    inference_engine = _load_engine(settings)
    use_case = FlowNormalizerUseCase(
        source=source,
        repository=repository,
        engine=inference_engine,
    )
    await use_case.execute()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())

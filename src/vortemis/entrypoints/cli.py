import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vortemis.application.use_cases.bayesian_pytorch_engine import BayesianPyTorchEngine
from vortemis.application.use_cases.flow_normalizer import FlowNormalizerUseCase
from vortemis.application.use_cases.training import train_and_export
from vortemis.banner import print_banner
from vortemis.config import Settings
from vortemis.infrastructure.persistence.auth import seed_default_operators
from vortemis.infrastructure.persistence.models import Base
from vortemis.infrastructure.persistence.postgres_repository import (
    PostgresFlowRepository,
)
from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource


def _load_engine(settings: Settings) -> BayesianPyTorchEngine | None:
    if not settings.model_path.exists():
        return None
    return BayesianPyTorchEngine(settings.model_path, epsilon=settings.epsilon)


def _ensure_model(settings: Settings) -> None:
    if settings.model_path.exists():
        return
    train_and_export(settings.model_path)


async def main() -> None:
    print_banner()
    settings = Settings.from_env()
    _ensure_model(settings)
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await seed_default_operators(session)
        await session.commit()
    repository = PostgresFlowRepository(session_factory, epsilon=settings.epsilon)
    inference_engine = _load_engine(settings)
    source = ZeekTelemetrySource(settings.log_file)
    use_case = FlowNormalizerUseCase(
        source=source,
        repository=repository,
        engine=inference_engine,
    )
    await use_case.execute()
    if settings.continuous_mode:
        await _run_continuously(
            settings,
            repository,
            inference_engine,
            source.position,
        )
    await engine.dispose()


async def _run_continuously(
    settings: Settings,
    repository: PostgresFlowRepository,
    inference_engine: BayesianPyTorchEngine | None,
    start_offset: int,
) -> None:
    source = ZeekTelemetrySource(
        settings.log_file,
        follow=True,
        start_offset=start_offset,
    )
    use_case = FlowNormalizerUseCase(
        source=source,
        repository=repository,
        engine=inference_engine,
    )
    await use_case.execute(batch_size=1)


if __name__ == "__main__":
    asyncio.run(main())

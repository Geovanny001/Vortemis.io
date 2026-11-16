import asyncio
from pathlib import Path

from vortemis.application.use_cases.bayesian_pytorch_engine import BayesianPyTorchEngine
from vortemis.application.use_cases.flow_normalizer import FlowNormalizerUseCase
from vortemis.application.use_cases.training import train_and_export
from vortemis.banner import print_banner
from vortemis.config import Settings
from vortemis.infrastructure.persistence.auth import seed_default_operators
from vortemis.infrastructure.persistence.database import SqlDatabase
from vortemis.infrastructure.persistence.ingestion_state import (
    CheckpointRecorder,
    SqlIngestionState,
    resolve_resume_offset,
)
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
    database = SqlDatabase(settings.database_url)
    try:
        await database.create_schema()
        session_factory = database.session_factory
        async with session_factory() as session:
            await seed_default_operators(session)
            await session.commit()
        repository = PostgresFlowRepository(
            session_factory, epsilon=settings.epsilon
        )
        inference_engine = _load_engine(settings)
        state = SqlIngestionState(session_factory)
        start_offset = await resolve_resume_offset(state, settings.log_file)
        recorder = CheckpointRecorder(
            state, settings.log_file, initial_offset=start_offset
        )
        source = ZeekTelemetrySource(settings.log_file, start_offset=start_offset)
        use_case = FlowNormalizerUseCase(
            source=source,
            repository=repository,
            engine=inference_engine,
        )
        try:
            inserted = await use_case.execute(on_progress=recorder)
            print(f"flows persisted: {inserted}")
            if settings.continuous_mode:
                await _follow(
                    settings.log_file,
                    repository,
                    inference_engine,
                    recorder,
                    source.position,
                )
        finally:
            await recorder.flush()
    finally:
        await database.dispose()


async def _follow(
    log_file: Path,
    repository: PostgresFlowRepository,
    inference_engine: BayesianPyTorchEngine | None,
    recorder: CheckpointRecorder,
    start_offset: int,
) -> None:
    source = ZeekTelemetrySource(log_file, follow=True, start_offset=start_offset)
    use_case = FlowNormalizerUseCase(
        source=source,
        repository=repository,
        engine=inference_engine,
    )
    await use_case.execute(batch_size=1, on_progress=recorder)


if __name__ == "__main__":
    asyncio.run(main())

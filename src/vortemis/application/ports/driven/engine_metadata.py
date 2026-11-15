from typing import Protocol

from vortemis.application.queries.dto import ModelMetadata


class EngineMetadataPort(Protocol):
    async def load(self) -> ModelMetadata | None:
        ...

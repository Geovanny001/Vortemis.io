import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from vortemis.application.ports.driven.engine_metadata import EngineMetadataPort
from vortemis.application.queries.dto import ModelMetadata
from vortemis.application.use_cases.bayesian_pytorch_engine import load_checkpoint


class TorchEngineMetadata(EngineMetadataPort):
    def __init__(self, model_path: Path) -> None:
        self._model_path = model_path
        self._cached: ModelMetadata | None = None

    async def load(self) -> ModelMetadata | None:
        if self._cached is not None:
            return self._cached
        if not await asyncio.to_thread(self._model_path.exists):
            return None
        checkpoint = await asyncio.to_thread(load_checkpoint, self._model_path)
        architecture, feature_dim = _architecture(checkpoint["model_state_dict"])
        metadata = ModelMetadata(
            architecture=architecture,
            feature_dim=feature_dim,
            tau=float(checkpoint["tau"]),
            mean=tuple(float(value) for value in checkpoint["mu"]),
            std=tuple(float(value) for value in checkpoint["sigma"]),
        )
        self._cached = metadata
        return metadata


def _architecture(state: Mapping[str, Any]) -> tuple[str, int]:
    input_dim = int(state["encoder.0.weight"].shape[1])
    hidden = int(state["encoder.0.weight"].shape[0])
    latent = int(state["encoder.3.weight"].shape[0])
    layers = f"{input_dim} -> {hidden} -> {latent} -> {hidden} -> {input_dim}"
    return layers, input_dim

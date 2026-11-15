from pathlib import Path

import pytest
import torch

from vortemis.application.use_cases.bayesian_pytorch_engine import (
    FEATURE_DIM,
    TrafficAutoencoder,
)
from vortemis.infrastructure.model.metadata import TorchEngineMetadata


def _checkpoint(tmp_path: Path) -> Path:
    torch.manual_seed(0)
    model = TrafficAutoencoder(FEATURE_DIM)
    tensor = torch.randn(64, FEATURE_DIM)
    path = tmp_path / "ae.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "mu": tensor.mean(dim=0).numpy(),
            "sigma": tensor.std(dim=0).numpy(),
            "tau": 0.7,
        },
        path,
    )
    return path


async def test_metadata_reads_the_checkpoint(tmp_path: Path) -> None:
    metadata = await TorchEngineMetadata(_checkpoint(tmp_path)).load()

    assert metadata is not None
    assert metadata.architecture == "6 -> 16 -> 3 -> 16 -> 6"
    assert metadata.feature_dim == FEATURE_DIM
    assert metadata.tau == pytest.approx(0.7)
    assert len(metadata.mean) == FEATURE_DIM
    assert len(metadata.std) == FEATURE_DIM
    assert all(isinstance(value, float) for value in metadata.mean)


async def test_metadata_returns_none_when_the_checkpoint_is_missing(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.pt"

    assert await TorchEngineMetadata(missing).load() is None


async def test_metadata_is_cached_after_the_first_load(tmp_path: Path) -> None:
    path = _checkpoint(tmp_path)
    adapter = TorchEngineMetadata(path)

    first = await adapter.load()
    path.unlink()
    second = await adapter.load()

    assert first is not None
    assert second == first

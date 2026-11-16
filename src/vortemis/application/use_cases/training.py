from pathlib import Path

import numpy
import torch

from vortemis.application.features import FEATURE_DIM
from vortemis.application.use_cases.bayesian_pytorch_engine import (
    TrafficAutoencoder,
)

EPOCHS = 30
BATCH_SIZE = 256
LEARNING_RATE = 1e-3
TRAIN_SAMPLES = 50000
SEED = 42


def generate_legitimate_features(samples: int = TRAIN_SAMPLES) -> numpy.ndarray:
    rng = numpy.random.default_rng(SEED)
    iat_ms = rng.exponential(120.0, size=samples)
    orig_bytes = rng.lognormal(mean=5.0, sigma=1.2, size=samples)
    resp_bytes = rng.lognormal(mean=5.5, sigma=1.2, size=samples)
    duration = rng.exponential(0.5, size=samples)
    pcr = rng.normal(0.0, 0.15, size=samples)
    is_failed_conn = rng.choice([0.0, 1.0], size=samples, p=[0.95, 0.05])
    return numpy.stack(
        [
            numpy.log1p(iat_ms),
            numpy.log1p(orig_bytes),
            numpy.log1p(resp_bytes),
            numpy.log1p(duration),
            pcr,
            is_failed_conn,
        ],
        axis=1,
    ).astype("float32")


def train_and_export(
    model_path: Path,
    features: numpy.ndarray | None = None,
) -> None:
    torch.manual_seed(SEED)
    numpy.random.seed(SEED)
    data = features if features is not None else generate_legitimate_features()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    mu = data.mean(axis=0)
    sigma = data.std(axis=0)
    standardized = (data - mu) / (sigma + 1e-8)
    model = TrafficAutoencoder(FEATURE_DIM)
    _train(model, standardized, device)
    model.eval()
    with torch.no_grad():
        tensor = torch.from_numpy(standardized).to(device)
        error = ((tensor - model(tensor)) ** 2).mean(dim=1).cpu().numpy()
    tau = float(numpy.quantile(error, 0.95))
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "mu": mu.tolist(),
            "sigma": sigma.tolist(),
            "tau": tau,
        },
        model_path,
    )


def _train(
    model: TrafficAutoencoder,
    features: numpy.ndarray,
    device: torch.device,
) -> None:
    optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
    criterion = torch.nn.MSELoss()
    tensor = torch.from_numpy(features).to(device)
    model.to(device)
    model.train()
    sample_count = len(features)
    for _ in range(EPOCHS):
        permutation = torch.randperm(sample_count, device=device)
        for start in range(0, sample_count, BATCH_SIZE):
            indices = permutation[start : start + BATCH_SIZE]
            batch = tensor[indices]
            optimizer.zero_grad()
            reconstructed = model(batch)
            loss = criterion(reconstructed, batch)
            loss.backward()
            optimizer.step()

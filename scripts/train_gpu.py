import sys
from pathlib import Path

import numpy
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vortemis.application.use_cases.bayesian_pytorch_engine import (  # noqa: E402
    FEATURE_DIM,
    TrafficAutoencoder,
)

SEED = 42
EPOCHS = 30
BATCH_SIZE = 256
LEARNING_RATE = 1e-3
TRAIN_SAMPLES = 50000
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "vortemis_ae.pt"


def _generate_legitimate_features(samples: int) -> numpy.ndarray:
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


def _train(model: TrafficAutoencoder, features: numpy.ndarray, device: torch.device) -> None:
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


def main() -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(SEED)
    numpy.random.seed(SEED)
    features = _generate_legitimate_features(TRAIN_SAMPLES)
    mu = features.mean(axis=0)
    sigma = features.std(axis=0)
    standardized = (features - mu) / (sigma + 1e-8)
    model = TrafficAutoencoder(FEATURE_DIM)
    _train(model, standardized, device)
    model.eval()
    with torch.no_grad():
        tensor = torch.from_numpy(standardized).to(device)
        reconstructed = model(tensor)
        error = ((tensor - reconstructed) ** 2).mean(dim=1).cpu().numpy()
    tau = float(numpy.quantile(error, 0.95))
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "mu": mu,
            "sigma": sigma,
            "tau": tau,
        },
        MODEL_PATH,
    )
    print(f"Training complete on {device}. Model saved to {MODEL_PATH} (tau={tau:.6f})")


if __name__ == "__main__":
    main()

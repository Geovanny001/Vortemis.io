import numpy
import pytest
import torch

from vortemis.application.use_cases.bayesian_pytorch_engine import (
    FEATURE_DIM,
    BayesianPyTorchEngine,
    TrafficAutoencoder,
    build_feature_vector,
    classify_mitre_tactic,
)


def test_autoencoder_forward_preserves_shape() -> None:
    model = TrafficAutoencoder(FEATURE_DIM)
    tensor = torch.randn(32, FEATURE_DIM)
    assert model(tensor).shape == tensor.shape


def test_build_feature_vector_shape_and_values() -> None:
    vector = build_feature_vector(
        iat_ms=10.0,
        orig_bytes=100,
        resp_bytes=50,
        duration=1.0,
        conn_state="SF",
    )
    assert vector.shape == (FEATURE_DIM,)
    assert vector[4] == pytest.approx(50 / 151, abs=1e-4)
    assert vector[5] == 0.0

    failed = build_feature_vector(
        iat_ms=None,
        orig_bytes=40,
        resp_bytes=0,
        duration=0.01,
        conn_state="S0",
    )
    assert failed[0] == 0.0
    assert failed[5] == 1.0


def test_classify_mitre_exfiltration() -> None:
    assert classify_mitre_tactic(
        conn_state="SF",
        src_ip="1.1.1.1",
        dst_ip="2.2.2.2",
        dst_port=443,
        orig_bytes=50000,
        resp_bytes=1000,
        iat_ms=100.0,
        duration=1.0,
        pcr=0.96,
    ) == "TA0010"


def test_classify_mitre_lateral_movement() -> None:
    assert classify_mitre_tactic(
        conn_state="SF",
        src_ip="192.168.1.5",
        dst_ip="10.0.0.5",
        dst_port=445,
        orig_bytes=500,
        resp_bytes=500,
        iat_ms=100.0,
        duration=1.0,
        pcr=0.0,
    ) == "TA0008"


def test_classify_mitre_impact() -> None:
    assert classify_mitre_tactic(
        conn_state="RSTO",
        src_ip="1.1.1.1",
        dst_ip="2.2.2.2",
        dst_port=80,
        orig_bytes=100,
        resp_bytes=0,
        iat_ms=1.0,
        duration=0.01,
        pcr=1.0,
    ) == "TA0040"


def test_classify_mitre_reconnaissance() -> None:
    assert classify_mitre_tactic(
        conn_state="S0",
        src_ip="1.1.1.1",
        dst_ip="2.2.2.2",
        dst_port=80,
        orig_bytes=40,
        resp_bytes=0,
        iat_ms=100.0,
        duration=0.01,
        pcr=1.0,
    ) == "TA0043"


def test_classify_mitre_command_and_control() -> None:
    assert classify_mitre_tactic(
        conn_state="SF",
        src_ip="1.1.1.1",
        dst_ip="2.2.2.2",
        dst_port=443,
        orig_bytes=500,
        resp_bytes=500,
        iat_ms=10.0,
        duration=0.5,
        pcr=0.0,
    ) == "TA0011"


def test_classify_mitre_normal_returns_none() -> None:
    assert classify_mitre_tactic(
        conn_state="SF",
        src_ip="1.1.1.1",
        dst_ip="2.2.2.2",
        dst_port=12345,
        orig_bytes=500,
        resp_bytes=500,
        iat_ms=100.0,
        duration=1.0,
        pcr=0.0,
    ) is None


def test_engine_predict_returns_probabilities(tmp_path) -> None:
    torch.manual_seed(0)
    model = TrafficAutoencoder(FEATURE_DIM)
    tensor = torch.randn(128, FEATURE_DIM)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    criterion = torch.nn.MSELoss()
    model.train()
    for _ in range(10):
        optimizer.zero_grad()
        loss = criterion(model(tensor), tensor)
        loss.backward()
        optimizer.step()
    model.eval()
    with torch.no_grad():
        error = ((model(tensor) - tensor) ** 2).mean(dim=1).numpy()
    checkpoint_path = tmp_path / "ae.pt"
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "mu": tensor.mean(dim=0).numpy(),
            "sigma": tensor.std(dim=0).numpy(),
            "tau": float(numpy.quantile(error, 0.95)),
        },
        checkpoint_path,
    )

    engine = BayesianPyTorchEngine(checkpoint_path)
    features = numpy.random.default_rng(1).normal(size=(64, FEATURE_DIM)).astype("float32")
    probabilities = engine.predict(features)

    assert probabilities.shape == (64,)
    assert numpy.all((probabilities >= 0.0) & (probabilities <= 1.0))

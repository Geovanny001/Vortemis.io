import ipaddress
from pathlib import Path

import numpy
import torch
import torch.nn as nn

FEATURE_DIM = 6

_LATERAL_PORTS = {22, 135, 139, 445, 3389, 5985}
_C2_PORTS = {53, 80, 443, 8080, 8443}
_IMPACT_STATES = {"S0", "RSTO", "RSTR", "SH", "OTH"}
_RECON_STATES = {"S0", "REJ"}
_FAILED_STATES = {"S0", "REJ", "RSTO", "RSTR"}


class TrafficAutoencoder(nn.Module):
    def __init__(self, input_dim: int = FEATURE_DIM) -> None:
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 16),
            nn.BatchNorm1d(16),
            nn.GELU(),
            nn.Linear(16, 3),
        )
        self.decoder = nn.Sequential(
            nn.Linear(3, 16),
            nn.BatchNorm1d(16),
            nn.GELU(),
            nn.Linear(16, input_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.decoder(self.encoder(x))


class BayesianPyTorchEngine:
    def __init__(self, model_path: Path, epsilon: float = 0.70, k: float = 10.0) -> None:
        self._epsilon = epsilon
        self._k = k
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=False)
        self._model = TrafficAutoencoder(FEATURE_DIM)
        self._model.load_state_dict(checkpoint["model_state_dict"])
        self._model.eval()
        self._mu = numpy.asarray(checkpoint["mu"], dtype="float32")
        self._sigma = numpy.asarray(checkpoint["sigma"], dtype="float32")
        self._tau = float(checkpoint["tau"])

    @property
    def epsilon(self) -> float:
        return self._epsilon

    def predict(self, features: numpy.ndarray) -> numpy.ndarray:
        standardized = (features - self._mu) / (self._sigma + 1e-8)
        tensor = torch.from_numpy(standardized.astype("float32"))
        with torch.no_grad():
            reconstructed = self._model(tensor)
            error = ((tensor - reconstructed) ** 2).mean(dim=1).numpy()
        return 1.0 / (1.0 + numpy.exp(-self._k * (error - self._tau) / self._tau))


def build_feature_vector(
    *,
    iat_ms: float | None,
    orig_bytes: int,
    resp_bytes: int,
    duration: float,
    conn_state: str | None,
) -> numpy.ndarray:
    resolved_iat = iat_ms if iat_ms is not None else 0.0
    pcr = (orig_bytes - resp_bytes) / (orig_bytes + resp_bytes + 1.0)
    is_failed_conn = 1.0 if conn_state in _FAILED_STATES else 0.0
    return numpy.asarray(
        [
            numpy.log1p(resolved_iat),
            numpy.log1p(orig_bytes),
            numpy.log1p(resp_bytes),
            numpy.log1p(duration),
            pcr,
            is_failed_conn,
        ],
        dtype="float32",
    )


def classify_mitre_tactic(
    *,
    conn_state: str | None,
    src_ip: str,
    dst_ip: str,
    dst_port: int,
    orig_bytes: int,
    resp_bytes: int,
    iat_ms: float | None,
    duration: float,
    pcr: float,
) -> str | None:
    if conn_state == "SF" and pcr > 0.60 and orig_bytes >= 25000:
        return "TA0010"
    if _is_private_ip(src_ip) and _is_private_ip(dst_ip) and dst_port in _LATERAL_PORTS:
        return "TA0008"
    if iat_ms is not None and iat_ms < 2.0 and conn_state in _IMPACT_STATES:
        return "TA0040"
    if conn_state in _RECON_STATES and resp_bytes == 0 and duration < 0.05:
        return "TA0043"
    if (iat_ms is not None and iat_ms < 50.0 and orig_bytes < 1500) or dst_port in _C2_PORTS:
        return "TA0011"
    return None


def _is_private_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False

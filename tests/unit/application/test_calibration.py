import numpy
import pytest

from vortemis.application.calibration import (
    conn_state_array,
    derive_conn_state,
    is_attack_label,
    map_label_to_tactic,
    normalize_label,
    vectorize_features,
)
from vortemis.application.use_cases.bayesian_pytorch_engine import build_feature_vector


def test_normalize_label_handles_replacement_character() -> None:
    assert normalize_label("Web Attack \ufffd Brute Force") == "Web Attack - Brute Force"


def test_map_label_to_tactic() -> None:
    assert map_label_to_tactic("BENIGN") is None
    assert map_label_to_tactic("PortScan") == "TA0043"
    assert map_label_to_tactic("DDoS") == "TA0040"
    assert map_label_to_tactic("Bot") == "TA0011"
    assert map_label_to_tactic("Infiltration") == "TA0010"
    assert map_label_to_tactic("Web Attack \ufffd XSS") == "TA0008"


def test_is_attack_label() -> None:
    assert is_attack_label("BENIGN") is False
    assert is_attack_label("PortScan") is True


def test_derive_conn_state() -> None:
    assert derive_conn_state(rst=1, syn=0, ack=1, fin=0) == "RSTO"
    assert derive_conn_state(rst=0, syn=1, ack=0, fin=0) == "S0"
    assert derive_conn_state(rst=0, syn=0, ack=1, fin=0) == "SF"
    assert derive_conn_state(rst=0, syn=0, ack=0, fin=1) == "SF"
    assert derive_conn_state(rst=0, syn=0, ack=0, fin=0) == "OTH"


def test_conn_state_array_matches_scalar_derivation() -> None:
    states = conn_state_array(
        rst=numpy.array([1, 0, 0, 0]),
        syn=numpy.array([0, 1, 0, 0]),
        ack=numpy.array([1, 0, 1, 0]),
        fin=numpy.array([0, 0, 0, 1]),
    )

    assert states.tolist() == ["RSTO", "S0", "SF", "SF"]


def test_vectorize_features_matches_engine_feature_builder() -> None:
    features = vectorize_features(
        iat_ms=numpy.array([10.0, 0.0, 100.0]),
        orig_bytes=numpy.array([100.0, 0.0, 5000.0]),
        resp_bytes=numpy.array([50.0, 0.0, 8000.0]),
        duration=numpy.array([1.0, 0.01, 2.0]),
        conn_state=numpy.array(["SF", "S0", "SF"]),
    )

    expected = numpy.stack(
        [
            build_feature_vector(
                iat_ms=10.0,
                orig_bytes=100,
                resp_bytes=50,
                duration=1.0,
                conn_state="SF",
            ),
            build_feature_vector(
                iat_ms=None,
                orig_bytes=0,
                resp_bytes=0,
                duration=0.01,
                conn_state="S0",
            ),
            build_feature_vector(
                iat_ms=100.0,
                orig_bytes=5000,
                resp_bytes=8000,
                duration=2.0,
                conn_state="SF",
            ),
        ]
    )

    assert features == pytest.approx(expected)


def test_vectorize_features_marks_failed_connections() -> None:
    features = vectorize_features(
        iat_ms=numpy.array([1.0, 1.0]),
        orig_bytes=numpy.array([10.0, 10.0]),
        resp_bytes=numpy.array([10.0, 10.0]),
        duration=numpy.array([1.0, 1.0]),
        conn_state=numpy.array(["SF", "REJ"]),
    )

    assert features[0, 5] == 0.0
    assert features[1, 5] == 1.0

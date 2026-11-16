import subprocess
import sys

import numpy

from vortemis.application.features import FEATURE_DIM, build_feature_vector


def test_feature_vector_shape_and_dtype() -> None:
    vector = build_feature_vector(
        iat_ms=10.0,
        orig_bytes=100,
        resp_bytes=200,
        duration=1.5,
        conn_state="SF",
    )

    assert vector.shape == (FEATURE_DIM,)
    assert vector.dtype == numpy.float32
    assert vector[5] == 0.0


def test_missing_iat_and_failed_state_are_encoded() -> None:
    vector = build_feature_vector(
        iat_ms=None,
        orig_bytes=0,
        resp_bytes=0,
        duration=0.0,
        conn_state="S0",
    )

    assert vector[0] == 0.0
    assert vector[5] == 1.0


def test_features_module_does_not_load_torch() -> None:
    script = (
        "import sys; import vortemis.application.features; "
        "print('torch' in sys.modules)"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.strip() == "False"

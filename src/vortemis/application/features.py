import numpy

FEATURE_DIM = 6

_FAILED_STATES = {"S0", "REJ", "RSTO", "RSTR"}


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

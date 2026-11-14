from collections.abc import Sequence

import numpy

FAILED_CONN_STATES = frozenset({"S0", "REJ", "RSTO", "RSTR"})

_LABEL_TO_TACTIC = {
    "PortScan": "TA0043",
    "DDoS": "TA0040",
    "DoS Hulk": "TA0040",
    "DoS GoldenEye": "TA0040",
    "DoS slowloris": "TA0040",
    "DoS Slowhttptest": "TA0040",
    "Heartbleed": "TA0040",
    "Bot": "TA0011",
    "FTP-Patator": "TA0008",
    "SSH-Patator": "TA0008",
    "Web Attack - Brute Force": "TA0008",
    "Web Attack - XSS": "TA0008",
    "Web Attack - Sql Injection": "TA0008",
    "Infiltration": "TA0010",
}


def normalize_label(label: str) -> str:
    normalized = label.replace("\ufffd", "-").replace("\u2013", "-").replace("\u2014", "-")
    return " ".join(normalized.split())


def map_label_to_tactic(label: str) -> str | None:
    normalized = normalize_label(label)
    if normalized == "BENIGN":
        return None
    return _LABEL_TO_TACTIC.get(normalized)


def is_attack_label(label: str) -> bool:
    return normalize_label(label) != "BENIGN"


def derive_conn_state(rst: int, syn: int, ack: int, fin: int) -> str:
    if rst > 0:
        return "RSTO"
    if syn > 0 and ack == 0:
        return "S0"
    if ack > 0:
        return "SF"
    if fin > 0:
        return "SF"
    return "OTH"


def conn_state_array(
    rst: numpy.ndarray,
    syn: numpy.ndarray,
    ack: numpy.ndarray,
    fin: numpy.ndarray,
) -> numpy.ndarray:
    reset = numpy.asarray(rst)
    synchronize = numpy.asarray(syn)
    acknowledge = numpy.asarray(ack)
    finish = numpy.asarray(fin)
    return numpy.select(
        [
            reset > 0,
            (synchronize > 0) & (acknowledge == 0),
            acknowledge > 0,
            finish > 0,
        ],
        ["RSTO", "S0", "SF", "SF"],
        default="OTH",
    )


def vectorize_features(
    iat_ms: numpy.ndarray | Sequence[float],
    orig_bytes: numpy.ndarray | Sequence[float],
    resp_bytes: numpy.ndarray | Sequence[float],
    duration: numpy.ndarray | Sequence[float],
    conn_state: numpy.ndarray | Sequence[str],
) -> numpy.ndarray:
    iat = numpy.maximum(numpy.asarray(iat_ms, dtype="float64"), 0.0)
    orig = numpy.maximum(numpy.asarray(orig_bytes, dtype="float64"), 0.0)
    resp = numpy.maximum(numpy.asarray(resp_bytes, dtype="float64"), 0.0)
    seconds = numpy.maximum(numpy.asarray(duration, dtype="float64"), 0.0)
    states = numpy.asarray(conn_state)
    pcr = (orig - resp) / (orig + resp + 1.0)
    failed = numpy.isin(states, list(FAILED_CONN_STATES)).astype("float64")
    return numpy.stack(
        [
            numpy.log1p(iat),
            numpy.log1p(orig),
            numpy.log1p(resp),
            numpy.log1p(seconds),
            pcr,
            failed,
        ],
        axis=1,
    ).astype("float32")

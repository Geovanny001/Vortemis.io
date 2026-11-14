import argparse
from pathlib import Path

import numpy
import pandas

from vortemis.application.calibration import (
    conn_state_array,
    is_attack_label,
    map_label_to_tactic,
    normalize_label,
    vectorize_features,
)

_COLUMNS = {
    "Flow Duration": "flow_duration_us",
    "Total Length of Fwd Packets": "orig_bytes",
    "Total Length of Bwd Packets": "resp_bytes",
    "Flow IAT Mean": "iat_us",
    "RST Flag Count": "rst",
    "SYN Flag Count": "syn",
    "ACK Flag Count": "ack",
    "FIN Flag Count": "fin",
    "Label": "label",
}

_OUTPUT_COLUMNS = [
    "f_iat",
    "f_orig",
    "f_resp",
    "f_duration",
    "f_pcr",
    "f_failed",
    "iat_ms",
    "orig_bytes",
    "resp_bytes",
    "duration",
    "conn_state",
    "label",
    "is_attack",
    "mitre_tactic",
    "source_file",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-rows-per-file", type=int, default=None)
    return parser.parse_args()


def _prepare_file(path: Path, max_rows: int | None) -> pandas.DataFrame:
    frame = pandas.read_parquet(path, columns=list(_COLUMNS))
    if max_rows is not None:
        frame = frame.head(max_rows)
    frame = frame.rename(columns=_COLUMNS)
    frame = frame.replace([numpy.inf, -numpy.inf], numpy.nan).dropna()
    numeric = ["flow_duration_us", "orig_bytes", "resp_bytes", "iat_us", "rst", "syn", "ack", "fin"]
    for column in numeric:
        frame[column] = frame[column].astype("float64").clip(lower=0.0)
    frame["conn_state"] = conn_state_array(
        frame["rst"].to_numpy(),
        frame["syn"].to_numpy(),
        frame["ack"].to_numpy(),
        frame["fin"].to_numpy(),
    )
    frame["iat_ms"] = frame["iat_us"] / 1000.0
    frame["duration"] = frame["flow_duration_us"] / 1_000_000.0
    features = vectorize_features(
        iat_ms=frame["iat_ms"].to_numpy(),
        orig_bytes=frame["orig_bytes"].to_numpy(),
        resp_bytes=frame["resp_bytes"].to_numpy(),
        duration=frame["duration"].to_numpy(),
        conn_state=frame["conn_state"].to_numpy(),
    )
    for index, column in enumerate(
        ["f_iat", "f_orig", "f_resp", "f_duration", "f_pcr", "f_failed"]
    ):
        frame[column] = features[:, index]
    labels = frame["label"].unique()
    tactic_by_label = {label: map_label_to_tactic(str(label)) for label in labels}
    attack_by_label = {label: is_attack_label(str(label)) for label in labels}
    normalized_by_label = {label: normalize_label(str(label)) for label in labels}
    frame["mitre_tactic"] = frame["label"].map(tactic_by_label)
    frame["is_attack"] = frame["label"].map(attack_by_label)
    frame["label"] = frame["label"].map(normalized_by_label)
    frame["source_file"] = path.name
    return frame[_OUTPUT_COLUMNS]


def main() -> None:
    args = _parse_args()
    input_dir = Path(args.input_dir)
    output = Path(args.output)
    frames = [
        _prepare_file(path, args.max_rows_per_file)
        for path in sorted(input_dir.glob("*.parquet"))
    ]
    if not frames:
        raise SystemExit(f"No parquet files found in {input_dir}")
    prepared = pandas.concat(frames, ignore_index=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    prepared.to_parquet(output, index=False)
    attacks = prepared[prepared["is_attack"]]
    unknown = attacks[attacks["mitre_tactic"].isna()]["label"].value_counts()
    print("rows", len(prepared))
    print("benign", int((~prepared["is_attack"]).sum()))
    print("attacks", len(attacks))
    print("labels")
    print(prepared["label"].value_counts().to_string())
    print("tactics")
    print(attacks["mitre_tactic"].value_counts().to_string())
    if not unknown.empty:
        print("unmapped_attack_labels")
        print(unknown.to_string())
    print("output", output)


if __name__ == "__main__":
    main()

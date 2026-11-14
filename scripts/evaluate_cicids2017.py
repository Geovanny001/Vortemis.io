import argparse
import json
from pathlib import Path

import numpy
import pandas

from vortemis.application.evaluation import best_threshold, binary_metrics, roc_auc
from vortemis.application.use_cases.bayesian_pytorch_engine import (
    BayesianPyTorchEngine,
)

_FEATURE_COLUMNS = ["f_iat", "f_orig", "f_resp", "f_duration", "f_pcr", "f_failed"]
_METADATA_COLUMNS = ["is_attack", "mitre_tactic", "label"]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--epsilon", type=float, default=0.70)
    parser.add_argument("--max-benign", type=int, default=200000)
    parser.add_argument("--select-threshold", action="store_true")
    parser.add_argument("--max-fpr", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def _load(dataset: Path, max_benign: int, seed: int) -> pandas.DataFrame:
    frame = pandas.read_parquet(dataset, columns=_FEATURE_COLUMNS + _METADATA_COLUMNS)
    frame = frame.reset_index(drop=True)
    benign = frame[~frame["is_attack"]]
    attacks = frame[frame["is_attack"]]
    if max_benign > 0 and len(benign) > max_benign:
        benign = benign.sample(n=max_benign, random_state=seed)
    return pandas.concat([benign, attacks], ignore_index=True)


def _score(engine: BayesianPyTorchEngine, frame: pandas.DataFrame) -> numpy.ndarray:
    features = frame[_FEATURE_COLUMNS].to_numpy(dtype="float32")
    chunks = [
        engine.predict(features[start : start + 100000])
        for start in range(0, len(features), 100000)
    ]
    return numpy.concatenate(chunks)


def _split_mask(frame: pandas.DataFrame, seed: int) -> numpy.ndarray:
    rng = numpy.random.default_rng(seed)
    mask = numpy.zeros(len(frame), dtype=bool)
    attack = frame["is_attack"].to_numpy(dtype=bool)
    for class_mask in (attack, ~attack):
        indices = numpy.flatnonzero(class_mask)
        rng.shuffle(indices)
        mask[indices[: len(indices) // 2]] = True
    return mask


def _tactic_recall(
    frame: pandas.DataFrame,
    probabilities: numpy.ndarray,
    threshold: float,
) -> dict[str, dict[str, float]]:
    attacks = frame[frame["is_attack"]].copy()
    attacks["detected"] = probabilities[attacks.index] >= threshold
    grouped = attacks.groupby("mitre_tactic")["detected"].agg(["count", "mean"])
    return {
        str(tactic): {"count": float(row["count"]), "recall": float(row["mean"])}
        for tactic, row in grouped.iterrows()
    }


def _summary(
    frame: pandas.DataFrame,
    probabilities: numpy.ndarray,
    threshold: float,
) -> dict[str, object]:
    frame = frame.reset_index(drop=True)
    labels = frame["is_attack"].to_numpy(dtype=bool)
    predictions = probabilities >= threshold
    metrics = binary_metrics(labels, predictions)
    return {
        "threshold": threshold,
        "metrics": metrics,
        "roc_auc": roc_auc(labels, probabilities),
        "per_tactic": _tactic_recall(frame, probabilities, threshold),
    }


def main() -> None:
    args = _parse_args()
    frame = _load(Path(args.dataset), args.max_benign, args.seed)
    engine = BayesianPyTorchEngine(Path(args.model), epsilon=args.epsilon)
    probabilities = _score(engine, frame)
    result: dict[str, object] = {
        "dataset": str(args.dataset),
        "model": str(args.model),
        "rows": len(frame),
        "benign": int((~frame["is_attack"]).sum()),
        "attacks": int(frame["is_attack"].sum()),
        "default": _summary(frame, probabilities, args.epsilon),
    }
    if args.select_threshold:
        validation = _split_mask(frame, args.seed)
        threshold, validation_metrics = best_threshold(
            labels=frame.loc[validation, "is_attack"].to_numpy(dtype=bool),
            scores=probabilities[validation],
            max_fpr=args.max_fpr,
            default=args.epsilon,
        )
        result["threshold_selection"] = {
            "threshold": threshold,
            "validation_metrics": validation_metrics,
            "max_fpr": args.max_fpr,
        }
        result["selected"] = _summary(frame[~validation], probabilities[~validation], threshold)
    print(json.dumps(result, indent=2))
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

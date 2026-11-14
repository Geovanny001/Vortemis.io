import argparse
from pathlib import Path

import pandas

from vortemis.application.use_cases.bayesian_pytorch_engine import load_checkpoint
from vortemis.application.use_cases.training import train_and_export

_FEATURE_COLUMNS = ["f_iat", "f_orig", "f_resp", "f_duration", "f_pcr", "f_failed"]
_PROTECTED_MODEL = Path("models/vortemis_ae.pt")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--train-samples", type=int, default=300000)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    output = Path(args.output)
    if output.resolve() == _PROTECTED_MODEL.resolve():
        raise SystemExit("Refusing to overwrite models/vortemis_ae.pt")
    frame = pandas.read_parquet(args.dataset, columns=_FEATURE_COLUMNS + ["is_attack"])
    benign = frame[~frame["is_attack"]]
    if args.train_samples > 0 and len(benign) > args.train_samples:
        benign = benign.sample(n=args.train_samples, random_state=args.seed)
    features = benign[_FEATURE_COLUMNS].to_numpy(dtype="float32")
    train_and_export(output, features=features)
    checkpoint = load_checkpoint(output)
    print("training_rows", len(features))
    print("output", output)
    print("tau", float(checkpoint["tau"]))
    print("mu", [round(float(value), 4) for value in checkpoint["mu"]])
    print("sigma", [round(float(value), 4) for value in checkpoint["sigma"]])


if __name__ == "__main__":
    main()

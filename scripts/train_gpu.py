import argparse
import asyncio
import sys
from pathlib import Path

import numpy

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vortemis.application.use_cases.training import (
    generate_legitimate_features,
    train_and_export,
)

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "vortemis_ae.pt"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-log", dest="from_log", default=None)
    parser.add_argument("--log-file", dest="log_file", default=None)
    parser.add_argument("--output", default=str(MODEL_PATH))
    args = parser.parse_args()

    log_path = args.from_log or args.log_file
    if log_path:
        features = asyncio.run(_features_from_log(Path(log_path)))
    else:
        features = generate_legitimate_features()
    train_and_export(Path(args.output), features=features)
    print(f"Training complete. Model saved to {args.output}")


async def _features_from_log(log_path: Path) -> numpy.ndarray:
    import pandas

    from vortemis.application.features import build_feature_vector
    from vortemis.application.use_cases.mapper import ZeekFlowMapper
    from vortemis.infrastructure.zeek.telemetry_source import ZeekTelemetrySource

    mapper = ZeekFlowMapper()
    records = [record async for record in ZeekTelemetrySource(log_path).stream()]
    flows = [flow for flow in (mapper.to_flow(r.data) for r in records) if flow is not None]
    frame = pandas.DataFrame(
        {
            "epoch": [flow.ts.value.timestamp() for flow in flows],
            "src": [flow.src_ip.value for flow in flows],
        }
    ).sort_values(["src", "epoch"])
    frame["iat"] = frame.groupby("src")["epoch"].diff() * 1000.0
    iat = frame["iat"].reindex(range(len(flows))).to_numpy()
    return numpy.stack(
        [
            build_feature_vector(
                iat_ms=None if pandas.isna(iat[index]) else float(iat[index]),
                orig_bytes=flow.orig_bytes,
                resp_bytes=flow.resp_bytes,
                duration=flow.duration,
                conn_state=flow.conn_state,
            )
            for index, flow in enumerate(flows)
        ]
    ).astype("float32")


if __name__ == "__main__":
    main()

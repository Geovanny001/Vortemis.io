# Vortemis.io

Autonomous passive network anomaly detection and MITRE ATT&CK mapping platform.

## Description

Vortemis.io ingests massive volumes of passive network telemetry (Big Data) and
uses a PyTorch autoencoder with a Bayesian posterior to detect cybersecurity
anomalies and data exfiltration, going beyond static security rules. Each
detected anomaly is classified into a MITRE ATT&CK network tactic.

## Architecture & Tech Stack

- **Architecture:** Strict hexagonal architecture
  (`domain` -> `application` -> `infrastructure` -> `entrypoints`).
- **Python:** 3.14+
- **Telemetry:** Zeek TSV/JSON and a native `tshark` live packet sensor.
- **Inference:** PyTorch autoencoder (`6 -> 16 -> 3 -> 16 -> 6`) with a
  Gaussian posterior and a 95th-percentile threshold `tau`.
- **Data processing:** Pandas, NumPy.
- **Storage:** PostgreSQL 16 with SQLAlchemy 2.x (async) + asyncpg.
- **Web UI:** Streamlit, Plotly (dark SIEM console with native login + RBAC).
- **Terminal UI:** Textual, Rich.

## Prerequisites

- Docker and Docker Compose.
- Python 3.14+ and `uv` for local development.

## Quick Start with Docker

```bash
docker compose up --build
```

This starts:

- `db` - PostgreSQL 16 (port 5432).
- `seed_and_ingest` - seeds the catalog and operators, generates a Zeek sample
  and ingests it into the star schema.
- `dashboard` - Streamlit SIEM console (port 8501).

## Local Development

```bash
uv sync
uv run python scripts/seed_and_generate.py --generate-sample
uv run python -m vortemis.entrypoints.cli
uv run streamlit run src/vortemis/entrypoints/dashboard.py
```

The seed script only creates a header-only log by default. Pass
`--generate-sample` to create the 5000-flow demo log, and `--force` to
overwrite an existing log.

## Test Credentials

The seed script creates two operators (`soc_operators` table):

- Administrator: `admin_carles` / `VortemisAdmin2026!`
- SOC Analyst: `soc_analyst` / `VortemisAnalyst2026!`

Administrators may tune the probabilistic threshold `epsilon`; analysts have it
locked (read-only policy).

## Continuous Mode & Live Sensor

Set `CONTINUOUS_MODE=true` to keep the ingestion CLI following the Zeek log
(`follow=True`) and scoring new flows as they arrive.

To capture live packets with `tshark` and emit Zeek-compatible `conn.log` rows:

```bash
uv run python -m vortemis.infrastructure.zeek.live_sensor --interface wlan0 --log-file conn.log
```

If `tshark` is not installed the sensor exits gracefully.

## Terminal UI

```bash
uv run python -m vortemis.entrypoints.tui
```

Dark Textual console with five KPIs, a live `DataTable` refreshed every 2 s and
keyboard shortcuts: `[a]` anomalies only, `[+]`/`[-]` threshold, `[r]` refresh,
`[q]` quit.

## Environment Variables

See `.env.example` for the full list:

- `DATABASE_URL` - async SQLAlchemy PostgreSQL connection string.
- `LOG_FILE` - path to the Zeek log file to ingest.
- `MODEL_PATH` - path to the trained autoencoder checkpoint.
- `EPSILON` - posterior anomaly threshold.
- `CONTINUOUS_MODE` - `true` to follow the log continuously.

## Tests

```bash
uv run ruff check .
uv run pytest
```

## Calibration with CICIDS2017

The public CICIDS2017 dataset can be used to calibrate and evaluate the engine:

```bash
uv run python scripts/prepare_cicids2017.py --input-dir <raw-parquet-dir> --output <prepared.parquet>
uv run python scripts/train_cicids2017.py --dataset <prepared.parquet> --output models/vortemis_ae_cicids.pt
uv run python scripts/evaluate_cicids2017.py --dataset <prepared.parquet> --model models/vortemis_ae_cicids.pt --max-benign 200000 --select-threshold
```

The dataset and the experimental checkpoint are not versioned. See
`docs/evidence/2026-11-14-p1-cicids2017-baseline.md` for the baseline results.

## License & Copyright

Proprietary software developed by Carles Rivera and the Vortemis.io Team. See
the [LICENSE](LICENSE) file for details.

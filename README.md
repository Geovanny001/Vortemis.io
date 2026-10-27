# Vortemis SOC

Probabilistic passive SOC network telemetry analysis system.

## Description

Vortemis SOC is a probabilistic network telemetry analysis system with a
passive SOC approach. It ingests massive network telemetry (Big Data) and
uses Bayesian networks and mathematical inference to probabilistically detect
cybersecurity anomalies and data exfiltration, going beyond static security
rules.

## Architecture & Tech Stack

- **Architecture:** Strict hexagonal architecture
  (`domain` -> `application` -> `infrastructure` -> `entrypoints`).
- **Python:** 3.14+
- **Telemetry:** Zeek
- **Data processing:** Pandas, NumPy
- **Storage:** PostgreSQL 16 with SQLAlchemy 2.x (async) + asyncpg
- **API:** FastAPI, Uvicorn, PyJWT
- **UI:** Streamlit, Plotly

## Prerequisites

- Docker and Docker Compose.
- Python 3.14+ and `uv` for local development.

## Quick Start with Docker

```bash
docker compose up --build
```

This starts the full ecosystem:

- `db` - PostgreSQL 16 (port 5432).
- `seed_and_ingest` - generates 5000 synthetic Zeek flows and ingests them.
- `api` - FastAPI REST/WebSocket API (port 8000).
- `dashboard` - Streamlit SIEM dashboard (port 8501).

## Local Development

```bash
uv sync
uv run python scripts/seed_and_generate.py
uv run uvicorn vortemis.entrypoints.api:app --reload
uv run streamlit run src/vortemis/entrypoints/dashboard.py
```

## Environment Variables

See `.env.example` for the full list:

- `DATABASE_URL` - async SQLAlchemy PostgreSQL connection string.
- `LOG_FILE` - path to the Zeek log file to ingest.
- `JWT_SECRET` - secret used to sign JWT tokens.
- `API_PORT` - FastAPI port.
- `DASHBOARD_PORT` - Streamlit port.

## Seed Data

The seed script (`scripts/seed_and_generate.py`) generates
`data/samples/conn_massive.log` (5000 records) and populates the database with:

- MITRE ATT&CK tactics catalog.
- Two users:
  - `admin_carles` / `VortemisAdmin2026!` (admin)
  - `soc_analyst` / `VortemisAnalyst2026!` (analyst)

## API

Interactive docs are available at `http://localhost:8000/docs`.

Main endpoints:

- `POST /api/v1/auth/login`
- `GET /api/v1/health`
- `GET /api/v1/metrics/summary`
- `GET /api/v1/flows`
- `POST /api/v1/ingest/trigger`
- `PATCH /api/v1/config/threshold`
- `WEBSOCKET /ws/alerts`

A Postman collection is available at
`docs/vortemis_postman_collection.json`.

## License & Copyright

Proprietary software developed by Carles Rivera and Contributors. See the
[LICENSE](LICENSE) file for details.

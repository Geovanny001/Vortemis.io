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
- **Storage:** PostgreSQL 16 with SQLAlchemy 2.x (async)

## License & Copyright

Proprietary software developed by Carles Rivera and Contributors. See the
[LICENSE](LICENSE) file for details.

# ROADMAP — Vortemis (Mega Upgrade: arquitectura pura PyTorch)

Fuente de verdad: `Context_vortemis_puro.md` (especificación original). Objetivo: reemplazar la API REST por el motor PyTorch fuera de banda.

## Progreso (commit `04aa936`)
- [x] Fase 8 (parcial): `bayesian_pytorch_engine.py` con `TrafficAutoencoder`, `BayesianPyTorchEngine` (carga `.pt`, predice P(anomalía)) y `classify_mitre_tactic` (5 reglas). Smoke-test verde.
- [x] Fase 9: `scripts/train_gpu.py` (CUDA) y `scripts/generate_zeek_traffic.py` (10k flujos con 5 campañas MITRE).
- [x] Fase 11: capa REST eliminada (`api.py`, `security.py`, `SocUser`, FastAPI/JWT del pyproject, servicio `api` del compose).
- [x] Fase 8 (resto): motor conectado en `flow_normalizer.py` (IAT por src_ip, PCR, is_failed_conn, vector 6-dim) y `postgres_repository.py` (usa `anomaly_probability` + `mitre_tactic`).
- [x] Fase 10 (parcial): `anomaly_probability` en el modelo (pendiente renombrar a `protocol_id`/`state_id`/`INET`/`ts_start` si se quiere match 100% con spec).
- [x] Fase 12: dashboard Sección 6 (sin auth, filtro MITRE, ε=0.70, línea en histograma, KPIs por táctica).
- [x] Fase 13 (parcial): `config.py` (`Settings.from_env`), `banner.py`, Dockerfile con torch CPU, `.env.example` con `MODEL_PATH`/`EPSILON`.
- [x] Tests: `test_pytorch_mitre_engine.py` (modelo, features, 5 reglas MITRE, predict).
- [ ] Fase 13 (resto opcional): refactor de estructura (`infrastructure/ingestion/zeek_source.py`, `infrastructure/persistence/database.py`) — renombrar directorios e imports.

## Cómo retomar (para una sesión nueva)
1. Lee `Context_vortemis_puro.md` (spec) y `docs/DECISIONS.md`.
2. `uv sync` (torch CPU ya en pyproject con índice `pytorch-cpu`).
3. Siguiente paso concreto: **Fase 8 (resto) + Fase 10** — actualizar `flow_normalizer.py` (per-src_ip IAT, PCR, is_failed_conn, vector 6-dim) y `postgres_repository.py` (usar `BayesianPyTorchEngine` + `classify_mitre_tactic` en vez de la heurística vieja).

## Estado previo (Fases 0-7, ya en `develop`)
- Hexagonal, dominio puro, puertos, adaptador Zeek, normalizador (iat_ms), persistencia estrella, API REST + JWT (a eliminar), dashboard SIEM, seeds.
- `git log`: último commit `7d8ff8d` (Fase 7 full-stack).

## Fases del Mega Upgrade (pendientes)

### Fase 8 — Núcleo PyTorch (inferencia)
- `src/vortemis/application/use_cases/bayesian_pytorch_engine.py`:
  - `TrafficAutoencoder` (6 -> 16 -> 3 -> 16 -> 6, GELU + BatchNorm).
  - `BayesianPyTorchEngine`: carga `models/vortemis_ae.pt`, `model.eval()`, `torch.no_grad()`, calcula error de reconstrucción y `P(anomalía)` con sigmoide logística sobre tau.
  - Clasificador de 5 reglas MITRE de red: TA0010, TA0008, TA0040, TA0043, TA0011.
- Feature engineering en `flow_normalizer.py`: vector de 6 dims (log1p iat/bytes/duration, PCR, is_failed_conn), z-score con mu/sigma del .pt, `torch.from_numpy`.

### Fase 9 — Entrenamiento y generador (corren en la PC con GPU)
- `scripts/train_gpu.py`: entrena en CUDA (RTX 5050), guarda `models/vortemis_ae.pt` (pesos + mu/sigma/tau).
- `scripts/generate_zeek_traffic.py`: genera dataset de 50k flujos legítimos + `conn_realistic.log` (10k) con los 5 vectores MITRE.

### Fase 10 — Esquema estrella definitivo
- `models.py`: `dim_protocols(protocol_id, protocol_name, description)`, `dim_conn_states(state_id, state_code, description)`, `dim_mitre_tactics(tactic_id, mitre_id, tactic_name)`, `fact_network_flows(flow_id UUID PK, ts_start, src_ip/dst_ip INET, ports, protocol_id, state_id, tactic_id, iat_ms, orig/resp_bytes, anomaly_probability)`.
- `postgres_repository.py`: usa `BayesianPyTorchEngine` + 5 reglas MITRE.

### Fase 11 — Eliminar capa REST (arquitectura pura)
- Borrar `api.py`, `security.py`, `soc_users`, deps JWT/FastAPI, servicio `api` en compose. (PENDIENTE de confirmación del usuario: ¿eliminar o conservar?)

### Fase 12 — Dashboard SIEM según Sección 6
- Filtro MITRE Tactic, umbral ε=0.70, línea vertical en histograma de probabilidad, 5 KPIs según tácticas.

### Fase 13 — Refactor de estructura + Docker
- `config.py`, `banner.py`, `infrastructure/ingestion/zeek_source.py`, `infrastructure/persistence/database.py`.
- Dockerfile con `torch` CPU; compose con `app` (daemon) + `dashboard`.

## Reglas inamovibles (recordar siempre)
1. Regla 7: inglés absoluto en código, commits, UI.
2. Cero comentarios `#`.
3. Python 3.14+, tipado estricto, `Mapped[T]`.
4. Arquitectura hexagonal: `domain <- application <- infrastructure <- entrypoints`; `domain/` sin libs externas.
5. Ejecutar `ruff check .` y `pytest` en verde antes de avanzar de fase.
6. PyTorch: entrenar en GPU (otra PC), inferir en CPU (Docker). Yo genero el código; el `.pt` se entrena fuera.

## 2026-11-14 — Estabilización P0 de ingesta
- Plan: `docs/IMPROVEMENT_PLAN.md`
- Evidencia base: `docs/evidence/2026-11-14-p0-ingestion.md`
- Rama: `release/p0-ingestion`
- P0-01 a P0-08 completados con tests y evidencia.
- Docker build verificado en GitHub Actions.
- PRs #10, #11 y #12 fusionados.

## 2026-11-14 — P1 calibración CICIDS2017
- Rama: `feat/p1-cicids2017-calibration`
- Dataset: CICIDS2017 (`MachineLearningCSV` convertido a Parquet).
- Evidencia: `docs/evidence/2026-11-14-p1-cicids2017-baseline.md`
- Resultado: AUC 0.694 con el checkpoint original; 0.699 con benignos CICIDS; 0.868 con autoencoder 6→32→8→32→6; 0.998 con un modelo supervisado de diagnóstico.
- Estado: baseline completado; las mejoras de modelo quedan como trabajo futuro.
- Foco actual: UI y operaciones (dashboard, seguridad, retención y despliegue).
- Decisión pendiente: autoencoder más grande + features de comportamiento, o modelo híbrido.

## 2026-11-14 — UI/ops dashboard
- Rama: `feat/ui-ops-dashboard`
- Evidencia: `docs/evidence/2026-11-14-ui-ops-dashboard.md`
- Cambios: estado vacío, estado dinámico del sensor, KPIs con umbral real, placeholders, matriz MITRE en 2 columnas, inspector legible y purga admin.
- Ops: cabecera Zeek compartida, purga de telemetría, volumen del dashboard escribible y scripts de arranque corregidos.
- Validación: 99 tests verdes y dashboard `200 ok`.
- Próximo: revisión visual y luego logs estructurados, secretos, rate limiting y retención.

## 2026-11-14 — Ops/seguridad
- Rama: `feat/ops-security`
- Evidencia: `docs/evidence/2026-11-14-ops-security.md`
- Cambios: rate limiting de login, credenciales de operadores por entorno, rotación de contraseñas, healthcheck del dashboard, Caddyfile y guía de seguridad.
- Validación: 105 tests verdes; dashboard `200 ok`; `healthcheck.py` exit 0.
- Pendiente: rate limiter compartido, logs estructurados, auditoría, TLS real, retención e índices.

## 2026-11-14 — Separación UI/motor
- Rama: `feat/ui-engine-separation`
- Evidencia: `docs/evidence/2026-11-14-ui-engine-separation.md`
- Read side: DTOs, `FlowQueryPort`, `TelemetryReadService` y adaptadores SQL.
- Dashboard y TUI ya no importan SQLAlchemy, modelos ni repositorios.
- `MITRE_TACTICS` se movió a `application/mitre.py`.
- Validación: 108 tests verdes; dashboard `200 ok`.
- Próximo: filtros/paginación SQL, modularizar la UI y elegir la presentación (Streamlit, Flet/NiceGUI o React).
- Handoff de la jornada: `docs/handoff/2026-11-14.md`

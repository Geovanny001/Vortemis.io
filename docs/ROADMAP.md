# ROADMAP — Vortemis (Mega Upgrade: arquitectura pura PyTorch)

Fuente de verdad: `Context_vortemis_puro.md` (especificación original). Objetivo: reemplazar la API REST por el motor PyTorch fuera de banda.

## Progreso (commit `04aa936`)
- [x] Fase 8 (parcial): `bayesian_pytorch_engine.py` con `TrafficAutoencoder`, `BayesianPyTorchEngine` (carga `.pt`, predice P(anomalía)) y `classify_mitre_tactic` (5 reglas). Smoke-test verde.
- [x] Fase 9: `scripts/train_gpu.py` (CUDA) y `scripts/generate_zeek_traffic.py` (10k flujos con 5 campañas MITRE).
- [x] Fase 11: capa REST eliminada (`api.py`, `security.py`, `SocUser`, FastAPI/JWT del pyproject, servicio `api` del compose).
- [ ] Fase 8 (resto): conectar el motor en `flow_normalizer.py` y `postgres_repository.py` (hoy el repo usa heurística vieja, no PyTorch).
- [ ] Fase 10: esquema definitivo (`anomaly_probability`, `protocol_id`/`state_id`, `INET`, `ts_start`, checks).
- [ ] Fase 12: dashboard Sección 6 (quitar login, filtro MITRE, ε=0.70, línea en histograma).
- [ ] Fase 13: `config.py`, `banner.py`, refactor estructura, Dockerfile con torch CPU.
- [ ] Tests: `test_pytorch_mitre_engine.py`.

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

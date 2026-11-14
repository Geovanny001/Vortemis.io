# UI/ops — Dashboard polish and admin purge

- Fecha: 2026-11-14
- Rama: `feat/ui-ops-dashboard`
- Base: `develop` en `23b6b8c`
- Alcance: dashboard, purga administrativa y estado del sensor

## 1. Cambios de UI

- Estado vacío real: si no hay flujos, el dashboard muestra un panel con el comando del sensor y no intenta renderizar gráficos vacíos.
- Estado del sensor dinámico: `RECEIVING LIVE`, `IDLE`, `IDLE Ns` o `LOG MISSING` según la última escritura del log.
- KPIs calculados con el umbral real del sidebar, no con `0.70` fijo.
- Placeholders en los filtros de IP y puerto.
- Matriz MITRE en cuadrícula de 2 columnas.
- Selector de flujo legible:
  `[Risk: 94.2% | TA0043] origen -> destino:puerto (TCP)`.
- Inspector unificado:
  `Feature / Current Value / Z-Score / Status`.
- Manejo de `iat_ms` y `conn_state` nulos en el inspector.

## 2. Cambios de ops

- Nueva función `purge_telemetry`:
  - `TRUNCATE TABLE fact_network_flows RESTART IDENTITY` en PostgreSQL.
  - `DELETE FROM fact_network_flows` en SQLite.
  - Rewrite del log con la cabecera Zeek.
- Nueva cabecera compartida `ZEEK_CONN_HEADER` en `infrastructure/zeek/header.py`.
- Zona de peligro en el sidebar, solo para rol `admin`, con confirmación explícita.
- `docker-compose.yml`: el dashboard monta `data/samples` en modo escritura y tiene `restart: unless-stopped`.
- Scripts locales `start-all.ps1` y `stop-all.ps1`: corregido el filtro de procesos para detectar `entrypoints/dashboard.py` con `/` además de `\`.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
99 passed in 9.34s
```

Tests nuevos:

- `tests/integration/test_telemetry_maintenance.py`: purga flujos en SQLite y deja el log con solo cabeceras.
- `tests/unit/entrypoints/test_dashboard_smoke.py`:
  - Renderiza las 4 pestañas con datos.
  - Renderiza el estado vacío sin excepciones.

Runtime:

```text
Dashboard: http://127.0.0.1:8501 -> 200 ok
PostgreSQL: running
Flows: 5000
Anomalies: 4852
```

## 4. Archivos

- `src/vortemis/entrypoints/dashboard.py`
- `src/vortemis/infrastructure/persistence/maintenance.py`
- `src/vortemis/infrastructure/zeek/header.py`
- `src/vortemis/infrastructure/zeek/live_sensor.py`
- `docker-compose.yml`
- `tests/integration/test_telemetry_maintenance.py`
- `tests/unit/entrypoints/test_dashboard_smoke.py`

## 5. Próximo paso

- Revisión visual del dashboard en el navegador.
- Ops: logs estructurados, secretos por entorno, rate limiting de login y retención.
- La calibración del modelo queda documentada como trabajo futuro.

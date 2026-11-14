# Separación UI/motor — Read side

- Fecha: 2026-11-14
- Rama: `feat/ui-engine-separation`
- Base: `develop` en `4e1d755`
- Objetivo: desacoplar las presentaciones del motor y de PostgreSQL

## 1. Problema anterior

`dashboard.py` y `tui.py` importaban directamente:

- `FactNetworkFlow`, `DimProtocol`, `DimConnState`, `DimMitreTactic`
- `select`, `async_sessionmaker`, `create_async_engine`
- `authenticate_operator`
- `purge_telemetry`

La UI tenía SQL propio y la lógica estaba duplicada entre Streamlit y TUI.

## 2. Nueva arquitectura

```text
entrypoints/dashboard.py
entrypoints/tui.py
        │
        ▼
application/queries/telemetry.py  (TelemetryReadService)
        │
        ├── FlowQueryPort
        ├── OperatorAuthPort
        └── TelemetryMaintenancePort
                │
                ▼
infrastructure/persistence/
  SqlFlowQuery
  SqlOperatorAuth
  DatabaseTelemetryMaintenance
        │
        ▼
PostgreSQL / SQLite
```

### Piezas nuevas

- `application/queries/dto.py`: `FlowRecord`, `OperatorIdentity`.
- `application/ports/driven/flow_query.py`: `FlowQueryPort`.
- `application/ports/driven/operator_auth.py`: `OperatorAuthPort`.
- `application/ports/driven/telemetry_maintenance.py`: `TelemetryMaintenancePort`.
- `application/queries/telemetry.py`: `TelemetryReadService`.
- `infrastructure/persistence/flow_query.py`: `SqlFlowQuery`.
- `infrastructure/persistence/operator_auth.py`: `SqlOperatorAuth`.
- `infrastructure/persistence/telemetry_maintenance.py`: `DatabaseTelemetryMaintenance`.
- `infrastructure/persistence/session.py`: `session_scope`.
- `entrypoints/container.py`: `build_telemetry_service`.
- `application/mitre.py`: `MITRE_TACTICS` sale de infraestructura.

### Resultado

- El dashboard ya no importa SQLAlchemy, modelos ni repositorios.
- La TUI ya no importa SQLAlchemy ni modelos.
- Ambas usan el mismo `TelemetryReadService`.
- La TUI ahora muestra el `conn_state` real y los KPIs MITRE globales, no solo los últimos 50 flujos.
- El contrato de lectura queda listo para otra UI: desktop, Flet, NiceGUI o React.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
108 passed in 10.02s
```

Tests nuevos:

- `tests/unit/application/test_telemetry_read_service.py`: delegación de consultas, auth y purga.
- `tests/integration/test_flow_query.py`: DTOs, orden, conteos, tácticas y autenticación con SQLite.

Runtime:

```text
Dashboard: http://127.0.0.1:8501 -> 200 ok
healthcheck.py -> ok (exit 0)
PostgreSQL: running
Flows: 5000
```

## 4. Decisiones

- No se añadió API REST.
- La UI depende de puertos y DTOs, no de infraestructura.
- `entrypoints/container.py` es el composition root.
- No se creó otro repositorio. Cuando exista un frontend real, se decide monorepo o repo separado con este contrato ya estable.

## 5. Próximo paso

1. Filtros y paginación en SQL dentro de `FlowQueryPort`.
2. Separar `dashboard.py` en módulos de UI (`theme`, `components`, `pages`).
3. Elegir presentación: Streamlit pulido, Flet/NiceGUI desktop o React.
4. Mantener las mejoras de modelo y ops en la lista de futuro.

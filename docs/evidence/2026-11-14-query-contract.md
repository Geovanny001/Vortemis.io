# Motor: contrato de consulta

- Fecha: 2026-11-14
- Rama: `feat/query-contract`
- Base: `develop` en `104ce57`
- Objetivo: que cualquier UI consulte el motor con filtros, paginación y agregaciones en SQL.

## 1. Problema anterior

- `FlowQueryPort` exponía cuatro métodos sin filtros: `load_flows(limit)`, `count_flows`, `count_anomalies` y `count_by_tactic`.
- No había filtros por IP, puerto, protocolo, táctica, ventana temporal ni probabilidad.
- No había paginación: `load_flows(limit)` devolvía hasta 20 000 filas y la UI filtraba en pandas.
- No había agregaciones por host ni serie temporal.

## 2. Cambios

### Entrada: `FlowFilters`

`application/queries/filters.py`:

| Campo | Tipo |
|---|---|
| `since`, `until` | `datetime` con zona |
| `src_ip`, `dst_ip` | texto |
| `src_port`, `dst_port` | entero 1-65535 |
| `protocol` | texto, normalizado a minúsculas |
| `tactic` | texto, normalizado a mayúsculas |
| `min_probability` | 0.0-1.0 |

Validación en el constructor: zona horaria obligatoria, ventana coherente, puertos y probabilidad en rango.

### Salida: DTOs

- `FlowPage`: `records` y `next_cursor`.
- `SourceAggregate`: `src_ip`, `flows`, `anomalies`.
- `TimelinePoint`: `bucket_start`, `flows`, `anomalies`.

### Contrato

```python
search_flows(filters=None, limit=500, cursor=None) -> FlowPage
count_flows(filters=None) -> int
count_anomalies(threshold, filters=None) -> int
count_by_tactic(filters=None) -> dict[str, int]
top_sources(threshold, filters=None, limit=10) -> list[SourceAggregate]
timeline(threshold, bucket_seconds=60, filters=None) -> list[TimelinePoint]
```

`load_flows` desaparece: su sustituto es `search_flows`, que devuelve una página.

### Paginación

- Keyset sobre `(ts, flow_id)` en orden descendente, no `OFFSET`.
- El cursor codifica `ts` en ISO 8601 y el `flow_id`: `2023-11-14T22:18:20+00:00|<uuid>`.
- Se piden `limit + 1` filas para saber si hay página siguiente.
- Un cursor inválido lanza `ValueError`.

### Agregaciones

- `top_sources` agrupa por `src_ip` y cuenta anomalías con `CASE` sobre el umbral.
- `timeline` agrupa por cubo de `bucket_seconds`; el cubo se calcula por dialecto y se ordena ascendente.
- `count_*` aceptan los mismos filtros que la búsqueda.

### Presentaciones

- El dashboard y la TUI pasan a `search_flows(...).records`; dos líneas cada uno.
- El dashboard sigue cargando 20 000 filas: usarlas con filtros es el siguiente paso de UI.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
145 passed in 13.44s
```

Tests nuevos o ampliados:

- `tests/unit/application/test_filters.py`: normalización y rangos.
- `tests/unit/application/test_telemetry_read_service.py`: delegación de los seis métodos.
- `tests/integration/test_flow_query.py`: orden, paginación por cursor, filtros, conteos, `top_sources`, `timeline` y errores.

Prueba contra PostgreSQL real (`vortemis_query_check`, eliminada al terminar):

```text
page1=[8080, 22]
page2=[443, 53]
page3=[445]
ts_tz=UTC
window=[443]
prob=[22, 443, 53]
count=5
anomalies=3
tactics={'TA0010': 1, 'TA0008': 1, 'TA0043': 1}
top_sources=[('192.168.1.10', 2, 1), ('192.168.1.11', 1, 1)]
timeline=[('2023-11-14T22:10:00+00:00', 4, 3), ('2023-11-14T22:20:00+00:00', 1, 0)]
postgres_query_check=ok
```

## 4. Decisiones

- Keyset en vez de `OFFSET`: estable con ingesta continua y sin coste lineal al avanzar páginas.
- El cursor usa `(ts, flow_id)` porque `ts` puede repetirse y `flow_id` es único.
- `min_probability` sustituye a un flag de anomalía: el umbral es una decisión de la UI, no del ingesta.
- Los `datetime` se normalizan a UTC al salir del adaptador; SQLite los devuelve sin zona.
- El cubo temporal se calcula en SQL por dialecto para no cargar filas en memoria.
- `load_flows` se elimina en lugar de mantenerse como alias, para no dejar dos caminos.

## 5. Pendiente

1. `EngineMetadataPort` para sacar la lectura del checkpoint de las presentaciones.
2. Ciclo de vida compartido del engine en lugar de un pool por consulta.
3. Errores de aplicación tipados para las UIs.
4. Que el dashboard use filtros y `timeline` en lugar de 20 000 filas.
5. Retención y particionado de `fact_network_flows`.

# Motor: ingesta idempotente e índices

- Fecha: 2026-11-14
- Rama: `feat/engine-hardening`
- Base: `develop` en `1c9e324`
- Objetivo: que reiniciar o reingerir no duplique datos y que las consultas del motor no hagan full scan.

## 1. Problema anterior

- `NetworkFlow.flow_id` se generaba con `uuid4()`, así que el mismo flujo del log recibía un identificador distinto en cada ejecución.
- `cli.main()` releía el log desde el offset 0 en cada arranque.
- Resultado: cada reinicio del CLI insertaba de nuevo todo el histórico.

Además:

- `fact_network_flows` no tenía ningún índice además de la PK y el unique de `flow_id`.
- Cada lote consultaba las tres dimensiones (`protocol`, `conn_state`, `mitre_tactic`), incluso con lotes de un solo flujo en modo continuo.
- `session.add_all` insertaba sin comprobar duplicados.

## 2. Cambios

### Identidad determinista

Nuevo `domain/value_objects/flow_fingerprint.py`:

```python
flow_fingerprint(ts, src_ip, src_port, dst_ip, dst_port, protocol) -> UUID
```

- `uuid5` sobre `ts` con 6 decimales, la 5-tupla y el protocolo.
- El `ZeekFlowMapper` asigna ese identificador al construir el flujo.
- Dos ejecuciones del mismo log producen el mismo `flow_id`; un flujo distinto produce otro.

### Ingesta idempotente

- `PostgresFlowRepository.save_batch` usa `INSERT ... ON CONFLICT (flow_id) DO NOTHING` en PostgreSQL y en SQLite.
- Devuelve el número de filas insertadas; `FlowNormalizerUseCase.execute` lo agrega y lo devuelve.
- El CLI imprime `flows persisted: N`.
- Un lote con duplicados internos inserta una sola vez.
- `FlowRepositoryPort.save_batch` pasa de `-> None` a `-> int`.

### Índices

`fact_network_flows` ahora declara índices en:

- `ts`
- `src_ip`
- `is_anomaly`
- `anomaly_probability`
- `tactic_id`

### Caché de dimensiones

- Protocolos, estados de conexión y tácticas se cachean por proceso en el repositorio.
- El primer lote resuelve las dimensiones; los siguientes no repiten las consultas.
- En modo continuo con lotes de un flujo se eliminan tres consultas por flujo.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
117 passed in 10.90s
```

Tests nuevos:

- `tests/unit/domain/test_flow_fingerprint.py`: estabilidad y sensibilidad del fingerprint.
- `tests/unit/application/test_flow_mapper.py`: `flow_id` determinista y filas inválidas.
- `tests/unit/application/test_flow_normalizer.py`: reprocesar los mismos registros no duplica.
- `tests/integration/test_postgres_repository.py`: idempotencia entre lotes y dentro de un lote.

Prueba contra PostgreSQL real (`vortemis_engine_check`, eliminada al terminar):

```text
log_lines=5  unique_flows=4
first_run=4
second_run=4
flows persisted: 4
flows persisted: 0
indexes=ix_fact_network_flows_ts, ix_fact_network_flows_src_ip,
        ix_fact_network_flows_is_anomaly, ix_fact_network_flows_anomaly_probability,
        ix_fact_network_flows_tactic_id
postgres_check=ok
```

## 4. Decisiones

- La identidad del flujo es de dominio, no de infraestructura: cualquier adaptador que ingiera debe usar `flow_fingerprint`.
- La idempotencia se resuelve en la base de datos con `ON CONFLICT`, no en memoria.
- `save_batch` informa de los insertados para poder medir duplicados sin logs estructurados.
- Las dimensiones se cachean por proceso porque `MITRE_TACTICS` es fijo y los protocolos y estados son estables.
- Los datos existentes conservan sus `flow_id` aleatorios: la primera reingesta tras este cambio inserta una copia. Un purgado deja el esquema limpio.

## 5. Pendiente

1. Persistir el offset de ingesta para no releer el log completo al arrancar.
2. Introducir Alembic: `create_all` no añade índices ni columnas a tablas existentes.
3. Filtros, paginación y agregaciones en `FlowQueryPort`.
4. `EngineMetadataPort` para que ninguna presentación lea el checkpoint directamente.

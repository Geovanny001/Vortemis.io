# Motor: ingesta con estado y migraciones

- Fecha: 2026-11-14
- Rama: `feat/stateful-ingestion`
- Base: `develop` en `50b8a01`
- Objetivo: no releer el log completo en cada arranque y gestionar el esquema con migraciones.

## 1. Problema anterior

- `cli.main()` releía el log desde el offset 0 en cada ejecución.
- La idempotencia evitaba duplicados, pero el motor reprocesaba todo el histórico.
- El esquema solo se creaba con `Base.metadata.create_all`; no había forma de aplicar un cambio a una base existente.
- La purga truncaba los flujos y reescribía el log, pero no reiniciaba ningún estado de lectura.

## 2. Cambios

### Estado de ingesta

Nueva tabla `ingestion_state`:

| Columna | Uso |
|---|---|
| `source_path` | Ruta del log, clave única |
| `device`, `inode` | Identidad del archivo para detectar rotación |
| `offset` | Último byte confirmado |
| `updated_at` | Última escritura |

Piezas:

- `domain` no cambia.
- `application/ports/driving/telemetry_source.py`: el puerto expone `position`.
- `application/use_cases/flow_normalizer.py`: `execute` acepta `on_progress` y notifica el offset tras cada lote confirmado.
- `infrastructure/persistence/ingestion_state.py`: `SqlIngestionState`, `resolve_resume_offset` y `CheckpointRecorder`.
- `entrypoints/cli.py`: reanuda desde el offset guardado y registra el avance.
- `infrastructure/persistence/maintenance.py`: la purga borra `ingestion_state` además de truncar los flujos.

### Reanudación

- Si el checkpoint existe y la identidad del archivo coincide y el tamaño es mayor o igual al offset, se reanuda.
- Si el archivo se truncó, se rotó o desapareció, se empieza en 0.
- El checkpoint se escribe como máximo cada 5 segundos; al cerrar se fuerza el último offset.
- Perder hasta 5 segundos de offset solo reprocesa líneas, que el `flow_id` determinista descarta.

### Migraciones

- Dependencia `alembic` y configuración `alembic.ini` + `migrations/`.
- `migrations/env.py` toma `DATABASE_URL` del entorno y usa `Base.metadata`.
- Revisión inicial `0001` con las seis tablas, el unique de `flow_id`, los cinco índices y `ingestion_state`.
- La imagen Docker copia `alembic.ini` y `migrations/` para poder migrar dentro del contenedor.

## 3. Arranque de una base

| Situación | Comando |
|---|---|
| Base nueva gestionada por migraciones | `alembic upgrade head` |
| Base creada con `create_all` o anterior a Alembic | `alembic stamp head` una vez |
| Aplicar cambios pendientes | `alembic upgrade head` |
| Revertir todo | `alembic downgrade base` |

Detalle en `docs/ops/DATABASE.md`.

## 4. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
129 passed in 11.66s
```

Tests nuevos:

- `tests/integration/test_ingestion_state.py`: roundtrip, upsert por fuente, reanudación, truncado, rotación, throttling y no reinicio del offset.
- `tests/integration/test_cli_resume.py`: el CLI reanuda y no reprocesa; tras truncar, vuelve a leer.
- `tests/integration/test_migrations.py`: la migración crea exactamente las tablas e índices de `Base.metadata`.
- `tests/unit/application/test_flow_normalizer.py`: `on_progress` recibe el offset tras cada lote.
- `tests/integration/test_telemetry_maintenance.py`: la purga borra el estado de ingesta.

Prueba contra PostgreSQL real (`vortemis_state_check`, eliminada al terminar):

```text
migration=applied
flows persisted: 3 | flows=3 offset=356  states=1 size=508
flows persisted: 2 | flows=5 offset=508  size=508
flows persisted: 0 | flows=5 offset=508  size=508
flows persisted: 1 | flows=6 offset=205  size=205
downgrade=ok
state_check=ok
```

Lectura: primera pasada 3 flujos; dos líneas nuevas, 2 flujos; sin cambios, 0; log truncado, reprocesa y suma 1.

## 5. Decisiones

- El estado se guarda en la base, no en un archivo local, para que el motor sea portable entre presentaciones y despliegues.
- La identidad del archivo se comprueba con `device` e `inode`; si el sistema no los expone, se acepta el offset.
- El checkpoint se limita a una escritura cada 5 segundos para no añadir una escritura por flujo en modo continuo.
- La idempotencia sigue siendo la garantía de corrección; el offset es una optimización.
- La purga reinicia el estado porque reescribe el log.
- Las bases existentes se adoptan con `alembic stamp head`, no con `upgrade`.
- `create_all` sigue siendo el arranque rápido; Alembic gestiona la evolución.

## 6. Pendiente

1. Filtros, paginación y agregaciones en `FlowQueryPort`.
2. `EngineMetadataPort` para sacar la lectura del checkpoint de las presentaciones.
3. Ciclo de vida compartido del engine en lugar de un pool por consulta.
4. Retención y particionado de `fact_network_flows`.

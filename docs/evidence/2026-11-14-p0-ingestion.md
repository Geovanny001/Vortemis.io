# Evidencia base — P0 de ingesta

- Fecha: 2026-11-14
- Rama: `release/p0-ingestion`
- Base: `develop` en `1e393c9`
- Entorno: Windows, Python 3.14.3, `uv` 0.13.8, PostgreSQL 16.16 portable
- Repo local: `E:\Vortemis.io`
- Identidad de commits de esta rama: `Geo052 <carlesriveramarroquin@gmail.com>`
- Estado del árbol al iniciar: limpio

## 1. Checks base

### 1.1 Ruff

```text
$ python -m uv run ruff check .
All checks passed!
```

### 1.2 Pytest

```text
$ python -m uv run pytest
67 passed in 16.06s
```

### 1.3 PostgreSQL

```text
$ psql -h localhost -U vortemis -d vortemis -c "select count(*) from fact_network_flows;"
5000

$ psql -h localhost -U vortemis -d vortemis -c "select count(*) from fact_network_flows where is_anomaly;"
4509
```

Tácticas asignadas:

| MITRE | Nombre | Flujos |
|---|---|---:|
| TA0011 | Command and Control | 1364 |
| TA0008 | Lateral Movement | 148 |

### 1.4 Dashboard

```text
GET http://127.0.0.1:8501/_stcore/health
200 ok
```

## 2. Reproducción de bugs P0

### P0-01 — Doble ingesta en modo continuo

Con un `conn.log` de 5 filas y `CONTINUOUS_MODE=true`, el CLI lee el archivo completo en la ingesta inicial y luego la fuente `follow=True` vuelve a leerlo desde el inicio.

Resultado observado:

```text
facts = 10
distinct_flow_ids = 10
duplicate_natural_rows = 5
```

Esperado: `facts = 5`.

Referencias: `src/vortemis/entrypoints/cli.py:44`, `:59`, `:65`.

### P0-02 — IAT en cero en modo continuo

El IAT se calcula por lote y el modo continuo usa `batch_size=1`.

Resultado observado:

```text
IAT batch_size=1:  [None, None, None, None, None]
IAT batch_size=10: [None, 99.99990463256836, None, 99.99990463256836, None]
```

Esperado: en continuo, el segundo flujo de una misma IP debe tener IAT no nulo.

Referencias: `src/vortemis/application/use_cases/flow_normalizer.py:30-34`, `:59-60`.

### P0-03 — El follower no recupera truncados

Se siguió un archivo, se truncó mientras el lector estaba en EOF y se esperó 2.5 s. El lector quedó bloqueado y no hizo `seek(0)`.

Resultado observado:

```text
truncation: reader stuck after truncate, no seek(0)
```

Esperado: detectar `st_size < position` y reiniciar la lectura.

Referencias: `src/vortemis/infrastructure/zeek/telemetry_source.py:30-39`.

### P0-04 — Timestamps y UDP del sensor

Dos flujos TCP distintos produjeron el mismo timestamp, el del último paquete:

```text
live sensor ts column:       ['5.000000', '5.000000']
live sensor duration column: ['0.000000', '0.000000']
```

Un paquete UDP se parseó con puertos `0/0`, por lo que el mapper lo descartó:

```text
parsed UDP packet ports: 0 0
UDP flow mapped to NetworkFlow: False
```

Referencias: `src/vortemis/infrastructure/zeek/live_sensor.py:81`, `:83`, `:160`.

### P0-05 — La imagen Docker no contiene el modelo

Verificación estática:

```text
Dockerfile: COPY pyproject.toml, src, scripts
Dockerfile: no COPY models
docker-compose.yml: no CONTINUOUS_MODE
```

No se pudo verificar con `docker build` porque Docker no está instalado en el entorno actual.

Referencias: `Dockerfile:5-9`, `docker-compose.yml`.

### P0-06 — El seed pisa el log

`scripts/seed_and_generate.py` llama siempre a `generate_sample_file()`, que hace `write_text` sobre `data/samples/conn_massive.log`. En compose se ejecuta en cada arranque.

Referencias: `scripts/seed_and_generate.py:106-109`, `:138`.

### P0-07 — Checkpoint cargado con `weights_only=False`

Referencias: `src/vortemis/application/use_cases/bayesian_pytorch_engine.py:41`, `src/vortemis/entrypoints/dashboard.py:177`.

Riesgo: ejecución de código arbitrario si el `.pt` es manipulado.

### P0-08 — Descalibración del detector

Con el checkpoint actual:

| Caso | P(anomalía) | Resultado |
|---|---:|---|
| Normal, 148/245 bytes | 0.0007 | No |
| Normal, 500/800 bytes | 0.0001 | No |
| Normal, 1000/2000 bytes | 0.0016 | No |
| Normal, 5000/8000 bytes | 0.9943 | Sí, TA0011 |
| Normal, 20000/30000 bytes | 1.0000 | Sí, TA0011 |
| C2 sintético | 0.0001 | No |
| Lateral sintético | 0.0004 | No |

Sobre el dataset de demo del repo:

```text
flows = 5000
anomalies = 4509 (90.2%)
tactics = TA0011: 1364, TA0008: 148
```

Esto no es una métrica de precisión real, pero confirma que la calibración actual no es fiable.

## 3. Tests de regresión a añadir

| Test | Bug |
|---|---|
| `test_continuous_mode_does_not_reingest_existing_rows` | P0-01 |
| `test_iat_persists_across_batches` | P0-02 |
| `test_truncated_log_restarts_from_beginning` | P0-03 |
| `test_live_sensor_uses_flow_timestamp` | P0-04 |
| `test_live_sensor_udp_ports` | P0-04 |
| `test_seed_does_not_overwrite_existing_log` | P0-06 |
| `test_checkpoint_loads_with_weights_only` | P0-07 |

## 4. Evidencia por commit

Cada commit de esta rama debe incluir en su descripción o en este documento:

```text
Problema:
Comando de reproducción:
Resultado antes:
Resultado después:
Tests añadidos:
Archivos tocados:
Riesgos residuales:
```

## 5. Fixes aplicados (2026-11-14)

### P0-01 — Una sola lectura del log en modo continuo

Antes:

```text
initial_count = 10
expected = 5
```

Después:

```text
initial_count = 5
final_count = 6
```

El CLI ahora conserva la posición final de la fuente inicial y arranca el follower desde ese offset. También se añadió priming de cabeceras para que el parser TSV tenga `#fields` aunque empiece a leer al final del archivo.

Archivos:

- `src/vortemis/entrypoints/cli.py`
- `src/vortemis/infrastructure/zeek/telemetry_source.py`
- `tests/integration/test_cli_continuous.py`

### P0-02 — IAT persistente entre lotes

Antes:

```text
[None, None, None]
```

Después:

```text
[None, 1000.0, 1000.0]
```

El normalizador mantiene el último timestamp por IP de origen entre lotes. Se eliminó el cálculo por lote con pandas y se reemplazó por un estado explícito en el caso de uso.

Archivos:

- `src/vortemis/application/use_cases/flow_normalizer.py`
- `tests/unit/application/test_flow_normalizer.py`

## 6. Verificación final

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
69 passed in 7.34s
```

## 7. Fixes aplicados (P0-03 y P0-04)

### P0-03 — Truncado y rotación

Validación runtime:

```text
truncate: C1 C2 C3
```

El follower detecta `st_size < position` y hace `seek(0)`. Si cambia la identidad `(st_dev, st_ino)`, cierra y reabre el archivo. En Windows no se puede reemplazar un archivo mientras está abierto, así que la rotación se valida con un test que simula el cambio de inodo.

Archivos:

- `src/vortemis/infrastructure/zeek/telemetry_source.py`
- `tests/unit/infrastructure/test_follow_source.py`

### P0-04 — Timestamps y puertos UDP del sensor

Validación runtime:

```text
udp_ports: 5353 53
flow_timestamps: [1.0, 5.0]
```

El parser usa los campos TCP o UDP según el protocolo, descarta ICMP sin puertos y cada flujo renderizado usa su propio `first_ts`.

Archivos:

- `src/vortemis/infrastructure/zeek/live_sensor.py`
- `tests/unit/infrastructure/test_live_sensor.py`

## 8. Verificación final

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
74 passed in 7.35s
```

## 9. Fixes aplicados (P0-05, P0-06 y P0-07)

### P0-05 — Docker con modelo y modo continuo

- `Dockerfile`: instala torch antes de copiar el código, copia `models/` y define `MODEL_PATH=/app/models/vortemis_ae.pt`.
- `docker-compose.yml`: `CONTINUOUS_MODE: "true"`, `MODEL_PATH` y `restart: unless-stopped` para el ingestor.
- `seed_and_ingest` usa `--generate-sample`, que no sobrescribe un log existente.
- Validación estática: `tests/test_deployment.py`.
- Validación real en GitHub Actions: build de la imagen, `model_present` e `import_ok`.
- Run: https://github.com/Geovanny001/Vortemis.io/actions/runs/43639632568

### P0-06 — Seed no destructivo

Validación runtime en un directorio temporal:

```text
default_lines=8
default_preserved=True
sample_lines=5008
sample_preserved_without_force=True
force_restored=True
force_lines=5008
```

Comportamiento:

- Sin flags: crea un log solo con cabeceras si no existe; no toca un log existente.
- `--generate-sample`: genera 5000 flujos si el archivo no existe.
- `--generate-sample --force`: sobrescribe un log existente.

Archivos:

- `scripts/seed_and_generate.py`
- `tests/unit/scripts/test_seed_and_generate.py`
- `README.md`

### P0-07 — Checkpoint con carga segura

- `load_checkpoint` usa `weights_only=True` y allowlist de globals NumPy necesarios para el checkpoint actual.
- `training.py` guarda `mu` y `sigma` como listas planas para que los checkpoints nuevos no necesiten NumPy al cargar.
- El dashboard usa el mismo loader seguro.

Validación runtime:

```text
checkpoint_keys: ['model_state_dict', 'mu', 'sigma', 'tau']
tau: 0.7455
unsafe_loads=0
```

Archivos:

- `src/vortemis/application/use_cases/bayesian_pytorch_engine.py`
- `src/vortemis/application/use_cases/training.py`
- `src/vortemis/entrypoints/dashboard.py`
- `tests/unit/application/test_pytorch_mitre_engine.py`

## 10. Verificación final

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
83 passed in 7.74s
```

## 11. Próximo paso

1. Construir la imagen Docker cuando haya Docker disponible.
2. Publicar tags/releases por cada P0.
3. Actualizar el PR y marcarlo listo para revisión.

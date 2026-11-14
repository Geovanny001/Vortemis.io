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

## 5. Próximo paso

1. Crear los tests de regresión en rojo.
2. Implementar P0-01 y P0-02.
3. Ejecutar `ruff check .` y `pytest`.
4. Verificar con PostgreSQL y CLI.
5. Registrar la evidencia del fix en este documento.

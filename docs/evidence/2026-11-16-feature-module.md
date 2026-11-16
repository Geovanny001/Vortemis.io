# Motor: features separadas del modelo

- Fecha: 2026-11-16
- Rama: `refactor/feature-module`
- Base: `develop` en `85af5ca`
- Objetivo: que una presentación pueda construir el vector de features sin cargar PyTorch.

## 1. Problema anterior

`build_feature_vector` vivía en `application/use_cases/bayesian_pytorch_engine.py`, junto a `TrafficAutoencoder`, `load_checkpoint` y `BayesianPyTorchEngine`.

Ese módulo importa `torch` al cargarse. El dashboard necesitaba `build_feature_vector` para el inspector, así que importaba el módulo del modelo y cargaba PyTorch completo para mostrar una tabla.

Consecuencias:

- Arranque más lento de cualquier presentación.
- La UI dependía de un runtime de inferencia que no usa.
- Una futura app de escritorio o web habría arrastrado el mismo peso.

## 2. Cambios

### Módulo nuevo

`application/features.py`:

```python
FEATURE_DIM = 6

def build_feature_vector(*, iat_ms, orig_bytes, resp_bytes, duration, conn_state) -> numpy.ndarray
```

- Solo depende de NumPy.
- Conserva la codificación exacta: `log1p` de IAT, bytes y duración, PCR y flag de conexión fallida.

### Módulo del modelo

`bayesian_pytorch_engine.py`:

- Importa `FEATURE_DIM` desde `application/features.py`.
- Elimina `build_feature_vector` y `_FAILED_STATES`.
- Mantiene `TrafficAutoencoder`, `load_checkpoint`, `BayesianPyTorchEngine` y `classify_mitre_tactic`.

### Importadores actualizados

| Archivo | Cambio |
|---|---|
| `use_cases/flow_normalizer.py` | `build_feature_vector` desde `application.features`; `classify_mitre_tactic` sigue en el motor |
| `use_cases/training.py` | `FEATURE_DIM` desde `application.features` |
| `entrypoints/dashboard.py` | `build_feature_vector` desde `application.features`; ya no importa el módulo del modelo |
| `scripts/train_gpu.py` | Ruta de import actualizada |
| Tests | `FEATURE_DIM` y `build_feature_vector` desde el módulo nuevo |

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
152 passed in 12.87s

$ python -m uv run python -c "import sys; import vortemis.application.features; print('torch' in sys.modules)"
False
```

Tests nuevos:

- `tests/unit/application/test_features.py`: forma, dtype, IAT ausente, estado fallido y comprobación en subproceso de que el módulo no carga `torch`.
- `tests/unit/entrypoints/test_dashboard_smoke.py`: el dashboard no menciona `bayesian_pytorch_engine` ni `load_checkpoint`.

Los smoke tests del dashboard siguen ejecutando la app completa con el checkpoint real.

## 4. Decisiones

- Las features son una función pura de dominio técnico: entran seis valores, sale un vector; no necesita el runtime de inferencia.
- `FEATURE_DIM` vive con las features porque describe el vector, no la red.
- `classify_mitre_tactic` se queda en el motor: la ingesta ya carga el modelo para puntuar, así que no aporta separarlo.
- El límite se protege con tests, no solo con convención: un import accidental de `torch` rompe la suite.

## 5. Pendiente

1. Ciclo de vida compartido del engine en lugar de un pool por consulta.
2. Errores de aplicación tipados.
3. Que el dashboard use filtros y `timeline` en lugar de 20 000 filas.
4. Retención y particionado de `fact_network_flows`.
5. Perfil SQLite/desktop con composition root propio.

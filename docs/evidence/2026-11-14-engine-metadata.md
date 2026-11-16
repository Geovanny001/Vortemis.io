# Motor: metadata del motor

- Fecha: 2026-11-14
- Rama: `feat/engine-metadata`
- Base: `develop` en `706903c`
- Objetivo: que ninguna presentación lea el checkpoint ni importe PyTorch para mostrar el motor.

## 1. Problema anterior

`dashboard.py` hacía:

```python
from vortemis.application.use_cases.bayesian_pytorch_engine import (
    build_feature_vector,
    load_checkpoint,
)
...
def load_model_metadata(model_path: Path) -> dict | None:
    checkpoint = load_checkpoint(model_path)
    return {
        "tau": float(checkpoint["tau"]),
        "mu": numpy.asarray(checkpoint["mu"], dtype="float32"),
        "sigma": numpy.asarray(checkpoint["sigma"], dtype="float32"),
        "layers": "6 -> 16 -> 3 -> 16 -> 6",
    }
```

La presentación decidía cómo abrir el checkpoint, cómo convertirlo y qué arquitectura tenía. Cualquier UI nueva habría tenido que repetir ese código.

## 2. Cambios

### DTO

`application/queries/dto.py`:

```python
ModelMetadata(architecture, feature_dim, tau, mean, std)
```

- `mean` y `std` son tuplas de `float`, no arrays de NumPy.
- `architecture` se deriva del `state_dict`, no está escrita a mano.

### Puerto

`application/ports/driven/engine_metadata.py`:

```python
class EngineMetadataPort(Protocol):
    async def load(self) -> ModelMetadata | None: ...
```

`None` significa que el checkpoint no existe; la presentación decide cómo mostrarlo.

### Adaptador

`infrastructure/model/metadata.py`: `TorchEngineMetadata`.

- Carga con `load_checkpoint` y `weights_only=True`, la misma ruta segura que la ingesta.
- Deriva la arquitectura de `encoder.0.weight`, `encoder.3.weight` y el número de features.
- Cachea el resultado por proceso; el checkpoint no cambia durante una ejecución.
- La lectura del archivo y de `torch.load` se ejecuta con `asyncio.to_thread`.

### Composition root

`build_telemetry_service(database_url, model_path)` inyecta también el adaptador de metadata. El dashboard y la TUI pasan la ruta del modelo que ya resolvían desde el entorno.

### Presentación

- El dashboard llama `service.model_metadata()` y usa `metadata.tau`, `metadata.architecture`, `metadata.mean` y `metadata.std`.
- Los z-scores se calculan con pandas, sin importar NumPy.
- Se eliminan del dashboard `load_model_metadata`, `load_checkpoint` y `import numpy`.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
148 passed in 37.08s
```

Tests nuevos o ampliados:

- `tests/unit/infrastructure/test_engine_metadata.py`: lectura del checkpoint, arquitectura derivada, checkpoint ausente y caché.
- `tests/unit/application/test_telemetry_read_service.py`: delegación de `model_metadata`.
- Los smoke tests del dashboard siguen ejecutando la app completa contra SQLite con el checkpoint real.

## 4. Decisiones

- La metadata es un DTO de aplicación, no un `dict` del checkpoint.
- La arquitectura se deriva del modelo para que un checkpoint distinto no muestre datos falsos.
- `epsilon` no forma parte de la metadata: es configuración de ejecución, no del modelo.
- El adaptador devuelve `None` en lugar de lanzar si falta el checkpoint; la UI ya distingue ese caso.
- La caché es por proceso porque el archivo no cambia durante una sesión.

## 5. Pendiente

1. `build_feature_vector` sigue viviendo en `bayesian_pytorch_engine`, así que el dashboard aún importa PyTorch de forma transitiva. Moverlo a un módulo puro de features es el siguiente paso.
2. Ciclo de vida compartido del engine en lugar de un pool por consulta.
3. Errores de aplicación tipados.
4. Que el dashboard use filtros y `timeline` en lugar de 20 000 filas.
5. Retención y particionado de `fact_network_flows`.

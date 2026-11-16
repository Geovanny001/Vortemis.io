# API: artefacto OpenAPI y servicio en Compose

- Fecha: 2026-11-16
- Rama: `chore/api-artifacts-compose`
- Base: `develop` en `e348fed`
- Objetivo: publicar el contrato como archivo y poder levantar la API con el resto del stack.

## 1. Problema anterior

- El contrato solo existía en `/openapi.json` de una instancia en ejecución.
- Un frontend no tenía un archivo estable que versionar.
- Compose levantaba base de datos, ingesta y dashboard, pero no la API.

## 2. Cambios

### Artefacto OpenAPI

- `scripts/export_openapi.py` escribe `docs/openapi.json` con `sort_keys` e indentación fija.
- El archivo se versiona en el repo.
- `tests/unit/test_openapi_artifact.py` falla si el archivo no coincide con `app.openapi()`.
- El workflow de CI ejecuta el script dentro de la imagen y sube `openapi` como artefacto del run.

### Servicio `api` en Compose

```yaml
api:
  build: .
  command: sh -c "alembic upgrade head || alembic stamp head; uvicorn vortemis.entrypoints.api:app --host 0.0.0.0 --port 8000"
  ports:
    - "8000:8000"
  healthcheck:
    test: ["CMD", "python", "scripts/healthcheck.py"]
```

- `HEALTHCHECK_URL=http://127.0.0.1:8000/v1/health`.
- `depends_on` la base de datos sana.
- CORS y TTL configurables por entorno con los valores por defecto del `.env.example`.
- `alembic upgrade head || alembic stamp head` cubre base nueva (upgrade) y base creada con `create_all` (adopción).
- Reutiliza `scripts/healthcheck.py`, sin script nuevo.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
192 passed in 21.92s

$ python -m uv run python scripts/export_openapi.py
E:\Vortemis.io\docs\openapi.json
```

Comprobaciones estáticas nuevas:

- `tests/test_deployment.py`: el servicio `api`, el puerto `8000`, el healthcheck y la subida del artefacto en CI.
- `tests/unit/test_openapi_artifact.py`: el archivo versionado coincide con el esquema de la app.

El build de Docker con el paso de exportación se valida en el CI del PR, porque Docker no está instalado en local.

## 4. Decisiones

- El contrato se versiona en el repo en lugar de generarse solo en runtime: el frontend necesita un archivo fijo.
- Un test de igualdad evita el drift entre código y `openapi.json`.
- La CI exporta dentro de la imagen: usa exactamente las dependencias del despliegue.
- El servicio `api` comparte imagen con el resto; no hay Dockerfile aparte.
- El healthcheck es HTTP y sin datos, igual que el del dashboard.
- `upgrade || stamp` es una concesión al arranque: cualquier base existente se adopta; las migraciones nuevas se aplican.

## 5. Pendiente

1. Adjuntar `openapi.json` al release de GitHub, no solo al run de CI.
2. Auditoría de logins y escrituras.
3. Limpieza programada de `api_tokens` expirados y de `login_attempts` antiguos.
4. Endpoint de métricas.

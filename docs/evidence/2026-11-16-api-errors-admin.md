# API: errores tipados y escritura admin

- Fecha: 2026-11-16
- Rama: `feat/api-errors-admin`
- Base: `develop` en `ac812de`
- Objetivo: mapear fallos de aplicación a HTTP y abrir las dos escrituras que el motor ya soporta.

## 1. Problema anterior

- `FlowFilters`, el cursor y los límites lanzaban `ValueError` genérico.
- La API traducía cada caso a mano y no distinguía entre entrada inválida, recurso ausente y error de base de datos.
- No había endpoints de escritura: la purga y la rotación de contraseñas solo existían en el dashboard y en scripts.

## 2. Cambios

### Errores de aplicación

`application/errors.py`:

```python
ApplicationError
InvalidQueryError(ValueError)
NotFoundError
PermissionDeniedError
```

- `InvalidQueryError` hereda de `ValueError` para no romper a los consumidores existentes.
- `FlowFilters`, el cursor, los límites y los umbrales lanzan `InvalidQueryError`.
- `SqlTokenStore` lanza `NotFoundError` si el operador no existe.

### Mapeo HTTP

| Excepción | Código |
|---|---|
| `InvalidQueryError` en filtros | 422 |
| `InvalidQueryError` en cursor | 400 |
| `NotFoundError` | 404 |
| `PermissionDeniedError` | 403 |
| `SQLAlchemyError` | 503 |

Los handlers viven en `create_app`, así que cualquier ruta futura hereda el mismo comportamiento.

### Administración

`OperatorAdminPort` + `SqlOperatorAdmin`.

```text
POST /v1/admin/purge                          -> 204
PUT  /v1/admin/operators/{username}/password  -> 204
```

- Ambas exigen rol `admin`; el resto recibe 403.
- La purga usa el mismo `TelemetryReadService.purge` del dashboard: trunca flujos, borra el estado de ingesta y reescribe el log.
- La rotación valida contraseña de 12 caracteres mínimo y permite cambiar el rol.
- El operador se resuelve en cada petición, así que un rol degradado pierde acceso al instante.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
178 passed in 17.93s
```

Tests nuevos:

- `tests/integration/test_api.py`: cursor inválido 400, purga admin 204, purga analyst 403, rotación de contraseña y login con la nueva.
- `tests/integration/test_token_store.py`: operador inexistente lanza `NotFoundError`.

Prueba contra PostgreSQL real con uvicorn (`vortemis_api_admin_check`, eliminada al terminar):

```text
before_flows=2
invalid_cursor=400
analyst_purge=403
rotate_status=204
new_login_role=analyst
purge_status=204
after_flows=0
```

## 4. Decisiones

- `InvalidQueryError` hereda de `ValueError`: los tests y llamadas existentes siguen funcionando.
- El mapeo se hace con handlers globales, no con `try/except` repetidos.
- La autorización se queda en la API: el motor autentica, la capa HTTP decide.
- La purga es irreversible y solo para `admin`; no se expone a `analyst`.
- La rotación de contraseña crea el operador si no existe, igual que el script de operaciones.

## 5. Pendiente

1. Refresh token con rotación.
2. Rate limit de login compartido entre instancias.
3. `openapi.json` como artefacto del release.
4. Servicio `api` en Compose con healthcheck.
5. Auditoría de purgas y rotaciones.

# API: refresh con rotación y rate limit compartido

- Fecha: 2026-11-16
- Rama: `feat/auth-hardening`
- Base: `develop` en `9fc0080`
- Objetivo: sesiones cortas revocables y bloqueo de login válido con varias instancias.

## 1. Problema anterior

- Un solo token de 12 horas: si se filtraba, la ventana de abuso era amplia y no había forma de renovarlo sin volver a pedir credenciales.
- El rate limit vivía en memoria por proceso: dos réplicas de la API duplicaban los intentos permitidos.

## 2. Cambios

### Refresh con rotación

- `api_tokens` gana `refresh_token_hash`, `previous_refresh_hash` y `refresh_expires_at` (migración `0003`).
- Login crea una sesión con access de 15 minutos y refresh de 30 días.
- `POST /v1/auth/refresh` rota ambos tokens en la misma fila:
  - el access anterior deja de resolver al instante;
  - el refresh anterior pasa a `previous_refresh_hash`.
- Reutilizar un refresh ya rotado revoca la sesión completa y devuelve `401`.
- Logout sigue revocando por access token.

### Rate limit compartido

- Nueva tabla `login_attempts` (`username`, `attempted_at`).
- `LoginThrottlePort` con implementación SQL.
- Cada intento fallido inserta una fila; el bloqueo se calcula contando la ventana de cinco minutos.
- `register_success` limpia los intentos del usuario.
- Las filas fuera de ventana se purgan en cada comprobación.
- El dashboard mantiene su `LoginLimiter` en memoria; la API usa la implementación SQL.

### Configuración

- `VORTEMIS_ACCESS_TTL_MINUTES` (15 por defecto).
- `VORTEMIS_REFRESH_TTL_DAYS` (30 por defecto).
- Se retira `VORTEMIS_TOKEN_TTL_HOURS`.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
188 passed in 20.74s
```

Tests nuevos:

- `tests/integration/test_token_store.py`: sesión, hash en reposo, expiración, rotación, reutilización y revocación.
- `tests/integration/test_login_throttle.py`: bloqueo, limpieza tras éxito, expiración del bloqueo y ventana.
- `tests/integration/test_api.py`: refresh, reutilización revoca la sesión y rate limit 429.

Prueba contra PostgreSQL real con uvicorn (`vortemis_auth_check`, eliminada al terminar):

```text
access_ttl=899 refresh_ttl=2591999
rotated_access_differs=True rotated_refresh_differs=True
new_access_me=admin_carles
old_access_status=401
replay_status=401
session_after_replay=401
throttle_status=429
```

## 4. Decisiones

- Access corto y refresh largo: menos exposición si se filtra un token.
- Rotación con detección de reutilización: un refresh robado y usado dos veces invalida la sesión.
- La rotación invalida también el access anterior; el cliente debe usar el par nuevo.
- Rate limit en base de datos en lugar de Redis: una tabla con dos columnas basta para el volumen de logins.
- La inserción por intento es atómica y sobrevive a reinicios y a múltiples instancias.
- El dashboard conserva su limiter en memoria porque no comparte sesiones con la API.

## 5. Pendiente

1. `openapi.json` como artefacto del release.
2. Servicio `api` en Compose con healthcheck.
3. Auditoría de logins, rotaciones y revocaciones.
4. Limpieza programada de `api_tokens` expirados.

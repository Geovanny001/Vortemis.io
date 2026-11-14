# Ops/seguridad — Login, credenciales y healthcheck

- Fecha: 2026-11-14
- Rama: `feat/ops-security`
- Base: `develop` en `2326933`
- Alcance: autenticación, rotación de credenciales, healthcheck y guía TLS

## 1. Cambios

### Rate limiting de login

- `LoginLimiter` en `infrastructure/persistence/login_limiter.py`.
- 5 intentos fallidos por usuario.
- Bloqueo de 5 minutos.
- Ventana de 5 minutos para reiniciar el contador.
- Un login exitoso limpia el estado.
- El dashboard muestra el tiempo restante de bloqueo.

Limitación: el contador vive en memoria del proceso. Con varios workers o réplicas hay que moverlo a Redis o PostgreSQL.

### Credenciales de operadores

- Los operadores por defecto se pueden sobrescribir con:
  - `VORTEMIS_ADMIN_USERNAME`
  - `VORTEMIS_ADMIN_PASSWORD`
  - `VORTEMIS_ANALYST_USERNAME`
  - `VORTEMIS_ANALYST_PASSWORD`
- `docker-compose.yml` acepta esas variables con defaults de desarrollo.
- `.env.example` documenta las variables.
- `scripts/set_operator_password.py` permite rotar la contraseña de un operador existente:
  ```bash
  uv run python scripts/set_operator_password.py --username admin_carles --role admin
  ```
- `operator_admin.set_operator_password` crea o actualiza el operador y re-hashea la contraseña.

### Healthcheck

- `scripts/healthcheck.py` consulta `/_stcore/health`.
- `docker-compose.yml` añade un healthcheck al servicio `dashboard`.
- Validación local: `healthcheck_exit=0`.

### TLS y operación

- `deploy/Caddyfile` como ejemplo de reverse proxy con TLS.
- `docs/ops/SECURITY.md` con checklist de rotación, red, TLS y pendientes.

## 2. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
105 passed in 9.84s
```

Runtime:

```text
Dashboard: http://127.0.0.1:8501 -> 200 ok
healthcheck.py -> ok (exit 0)
PostgreSQL: running
```

Tests nuevos:

- `tests/unit/infrastructure/test_login_limiter.py`: bloqueo, expiración, reset y usuarios separados.
- `tests/unit/infrastructure/test_auth.py`: siembra con credenciales desde entorno.
- `tests/integration/test_operator_admin.py`: creación y rotación de contraseña.

## 3. Limitaciones

- El rate limiter es por proceso; no sirve tal cual para múltiples réplicas.
- No hay MFA.
- No hay TLS ejecutándose localmente; solo el ejemplo de Caddy.
- No hay logs estructurados, métricas ni auditoría de eventos.
- Las credenciales de `.env.example` siguen siendo de desarrollo y deben rotarse.

## 4. Próximo paso

1. Logs estructurados en JSON y auditoría de login/purga.
2. Rate limiter compartido (Redis/PostgreSQL).
3. TLS real con Caddy/Nginx y firewall.
4. Retención, índices, deduplicación y Alembic.

# Seguridad y operación — Vortemis.io

Este documento cubre el primer bloque de hardening. No sustituye una auditoría formal.

## 1. Credenciales

Las credenciales de desarrollo siguen siendo las de `.env.example`. Antes de cualquier despliegue:

1. Cambiar la contraseña de PostgreSQL y actualizar `DATABASE_URL` en `.env` y `docker-compose.yml`.
2. Rotar las contraseñas de los operadores:
   ```bash
   uv run python scripts/set_operator_password.py --username admin_carles --role admin
   uv run python scripts/set_operator_password.py --username soc_analyst --role analyst
   ```
3. Rotar el token de GitHub y eliminarlo de `~/.git-credentials`; usar Git Credential Manager.
4. No versionar `.env`.

Para una base nueva, los operadores se siembran con estas variables:

```text
VORTEMIS_ADMIN_USERNAME
VORTEMIS_ADMIN_PASSWORD
VORTEMIS_ANALYST_USERNAME
VORTEMIS_ANALYST_PASSWORD
```

## 2. Login

- `LoginLimiter` bloquea una cuenta durante 5 minutos después de 5 intentos fallidos.
- El contador vive en memoria del proceso Streamlit.
- Si se despliega con varios workers o réplicas, mover el contador a Redis o a PostgreSQL.
- No hay autenticación multifactor todavía.

## 3. TLS y red

- No exponer `8501` ni `5432` directamente a Internet.
- Usar el ejemplo de `deploy/Caddyfile` detrás de un dominio con TLS.
- En producción, Streamlit debería escuchar en `127.0.0.1` y Caddy/Nginx hacer el proxy.
- Restringir el puerto de PostgreSQL a la red interna de Docker.

## 4. Healthcheck

El servicio `dashboard` de Compose usa:

```bash
python scripts/healthcheck.py
```

El script consulta `http://localhost:8501/_stcore/health` y sale con código 0 si responde 200.

## 5. Registro y auditoría

Pendiente:

- Logs estructurados en JSON.
- Métricas de ingesta, latencia y errores.
- Auditoría de login, purga y cambios de rol.
- Retención y rotación de logs.

## 6. Base de datos

Pendiente:

- Migraciones con Alembic.
- Índices en `ts`, `src_ip`, `is_anomaly` y `tactic_id`.
- Retención/particionado de `fact_network_flows`.
- Deduplicación de ingesta.

## 7. Checklist mínimo antes de exponer el sistema

- [ ] Contraseñas de PostgreSQL y operadores rotadas.
- [ ] Token de GitHub rotado.
- [ ] `.env` fuera de Git.
- [ ] TLS activo en el reverse proxy.
- [ ] `5432` no expuesto.
- [ ] `admin_carles` y `soc_analyst` con contraseñas nuevas.
- [ ] Healthcheck del dashboard en verde.

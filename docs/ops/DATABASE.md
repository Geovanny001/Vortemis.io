# Base de datos y migraciones

- Motor: PostgreSQL 16 en servidor, SQLite en pruebas y perfiles locales.
- Esquema: `src/vortemis/infrastructure/persistence/models.py`.
- Migraciones: `migrations/versions/`, con Alembic.

## 1. Comandos

```text
python -m uv run alembic upgrade head
python -m uv run alembic downgrade base
python -m uv run alembic current
python -m uv run alembic history
python -m uv run alembic revision --autogenerate -m "change"
```

La URL se toma de `DATABASE_URL`. Si no está definida, se usa la de `Settings`.

## 2. Arranque

| Situación | Acción |
|---|---|
| Base nueva | `alembic upgrade head` |
| Base creada con `create_all` | `alembic stamp head` una vez |
| Base anterior a Alembic | `alembic stamp head` una vez |
| Cambio de esquema pendiente | `alembic upgrade head` |
| Recrear desde cero | `alembic downgrade base` y `alembic upgrade head` |

`alembic stamp head` solo marca la versión; no crea ni modifica tablas. Usarlo únicamente cuando el esquema ya coincide con la última revisión.

## 3. Docker

La imagen incluye `alembic.ini` y `migrations/`.

```text
docker compose run --rm seed_and_ingest alembic upgrade head
docker compose run --rm seed_and_ingest alembic stamp head
```

## 4. Reglas

- Un cambio de esquema incluye su revisión en el mismo PR.
- La revisión inicial `0001` describe el esquema completo; no se edita después de publicarse.
- Los índices se declaran en el modelo y en la migración.
- `create_all` sigue disponible para tests y arranque rápido, pero no evoluciona esquemas.
- La purga de telemetría trunca `fact_network_flows` y borra `ingestion_state`; no toca dimensiones ni operadores.

## 5. Verificación

```text
python -m uv run alembic upgrade head
python -m uv run alembic downgrade base
python -m uv run pytest tests/integration/test_migrations.py
```

`tests/integration/test_migrations.py` compara las tablas e índices creados por la migración con `Base.metadata`.

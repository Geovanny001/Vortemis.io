# Vortemis.io

Motor de análisis probabilístico de tráfico de red con enfoque SOC pasivo.

## Qué busca el proyecto

Procesar telemetría de red masiva (Big Data) mediante **redes bayesianas e inferencia matemática** para detectar probabilísticamente anomalías de ciberseguridad y exfiltración de datos, superando las reglas de seguridad estáticas.

## Alcance actual (Sprint 1)

1. Ingesta asíncrona de logs Zeek.
2. Normalización vectorial con Pandas/NumPy.
3. Persistencia en esquema en estrella en PostgreSQL 16.

## Arquitectura

Arquitectura hexagonal estricta. El flujo de dependencias es:

```
domain -> application -> infrastructure -> entrypoints
```

- `domain`: conceptos puros de telemetría de red (sin dependencias externas).
- `application`: casos de uso y puertos (driving/driven).
- `infrastructure`: adaptadores (Zeek, PostgreSQL, etc.).
- `entrypoints`: puntos de entrada (CLI, API, etc.).

## Stack

- Python 3.14+
- SQLAlchemy 2.x (asíncrono) + asyncpg
- Pandas, NumPy, Pydantic
- Ruff (lint) y Pytest (tests)

## Estructura de ramas (Git Flow)

- `main`: producción estable.
- `develop`: integración (rama por defecto).
- `feature/<nombre>`: una rama por fase/feature, se mergea de vuelta a `develop`.

## Estado de fases

- [x] Fase 0 — Setup (pyproject, ruff, pytest)
- [x] Fase 1 — Dominio puro (value objects, NetworkFlow, errores)
- [x] Fase 2 — Puertos e interfaces de aplicación
- [ ] Fase 3 — Adaptador Zeek (ingesta asíncrona)
- [ ] Fase 4 — Normalización vectorial (Pandas/NumPy)
- [ ] Fase 5 — Persistencia PostgreSQL (esquema en estrella)

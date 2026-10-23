# Contexto Maestro del Proyecto: Vortemis

## Rol y Objetivo
Vortemis es un sistema de analisis probabilistico de trafico de red con enfoque SOC Pasivo.
Alcance actual: Sprint 1 (Ingesta asincrona de logs Zeek -> Normalizacion vectorial con Pandas/NumPy -> Persistencia en Esquema en Estrella en PostgreSQL 16).

## Reglas Inquebrantables de Arquitectura y Codigo
1. **Arquitectura Hexagonal Estricta:** El flujo de dependencias es `domain` <- `application` <- `infrastructure` <- `entrypoints` dentro del paquete `src/vortemis/`.
   - `src/vortemis/domain/` NO puede importar librerias externas (prohibido `pandas`, `numpy`, `sqlalchemy`, `pydantic`). Solo libreria estandar de Python.
2. **Estandar de Codigo:** Python 3.14+, tipado estricto y validacion con `ruff`.
3. **Cero Comentarios:** Prohibido escribir comentarios en linea (`#`) o bloques de comentarios dentro de los archivos de codigo. El codigo debe ser autoexplicativo mediante nombres claros y tipado.
4. **Privacidad por Diseno:** Descartar inmediatamente cualquier campo de `payload` crudo durante la ingesta.
5. **Persistencia Analitica:** Esquema en Estrella en PostgreSQL 16 (`fact_network_flows` como tabla de hechos y `dim_protocols`, `dim_conn_states`, `dim_mitre_tactics` como dimensiones) utilizando SQLAlchemy 2.x asincrono y `asyncpg`.
6. **Disciplina de Ejecucion:** No avanzar de fase sin antes ejecutar `ruff check` y `pytest` obteniendo resultados en verde.# OpenCode Context


## Estado del Proyecto
- [x] Fase 0: Setup, pyproject.toml, ruff, structlog base.
- [x] Fase 1: Dominio puro (Value Objects, NetworkFlow, DomainValidationError) con 23 tests en verde.
- [x] Fase 2: Capa de Aplicación - Puertos e Interfaces (Driving y Driven).
- [ ] Fase 3: Infraestructura - Adaptador Zeek (Streaming asíncrono y Parsers TSV/JSON).
- [ ] Fase 4: Caso de Uso - Normalizador Vectorial (Pandas/NumPy, IAT y doble salida).
- [ ] Fase 5: Infraestructura - Persistencia PostgreSQL (Esquema en Estrella y SQLAlchemy asíncrono).

## Especificación Fase 2 (Capa de Aplicación: Puertos)
1. **Driving Ports (`src/vortemis/application/ports/driving/`):**
   - `telemetry_source.py`: `TelemetrySourcePort` (Protocolo asíncrono con generador `stream() -> AsyncIterator[RawRecord]`).
   - `raw_record.py`: Tipo estructurado inmutable para la lectura cruda de líneas de logs.
2. **Driven Ports (`src/vortemis/application/ports/driven/`):**
   - `flow_repository.py`: `FlowRepositoryPort` (Protocolo asíncrono con método `save_batch(flows: list[NetworkFlow]) -> None`).
3. **Repositorio de Prueba (Falso/In-Memory):**
   - Implementar `InMemoryFlowRepository` en pruebas (`tests/doubles/in_memory_flow_repository.py`) para verificar que los puertos funcionen de forma aislada sin levantar Docker ni bases de datos todavía.
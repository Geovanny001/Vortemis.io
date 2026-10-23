# Contexto Maestro: Vortemis

## Objetivo del Sistema
Vortemis es un sistema de análisis probabilístico de telemetría de red con enfoque SOC Pasivo.
Alcance inicial (Sprint 1): Ingesta asíncrona de logs de Zeek -> Normalización vectorial en Pandas/NumPy -> Persistencia en Esquema en Estrella en PostgreSQL 16.

## Reglas Inquebrantables de Arquitectura y Código
1. **Arquitectura Hexagonal Estricta:**
   - La estructura vive en `src/vortemis/`.
   - Flujo unidireccional de dependencias: `domain` <- `application` <- `infrastructure` <- `entrypoints`.
   - `domain/` no puede importar librerías externas (prohibido `pandas`, `numpy`, `sqlalchemy`, `pydantic`). Solo biblioteca estándar de Python.
2. **Estándar Técnico:**
   - Python 3.14+ con tipado estricto.
   - Formateo y linting validado con `ruff`.
3. **Cero Comentarios en Código:**
   - Prohibido incluir comentarios en línea (`#`) o bloques de comentarios dentro de los archivos de código fuente. El código debe ser autoexplicativo a través de tipado e identificadores claros.
4. **Privacidad por Diseño:**
   - Descartar inmediatamente cualquier campo de `payload` crudo durante la ingesta.
5. **Persistencia Analítica:**
   - Esquema en Estrella en PostgreSQL 16 (`fact_network_flows` + dimensiones `dim_protocols`, `dim_conn_states`, `dim_mitre_tactics`) con SQLAlchemy 2.x asíncrono y `asyncpg`.
6. **Disciplina de Ejecución:**
   - No avanzar de fase sin ejecutar `ruff check` y `pytest` con resultado en verde.
7. **Idioma del Código:**
   - Todo el código fuente (clases, variables, métodos, puertos, nombres de archivos) y los mensajes de los commits de Git deben escribirse estrictamente en inglés. Las explicaciones, documentación y el chat se mantendrán en español.

## Estado del Proyecto
- [x] Fase 0: Setup, pyproject.toml, ruff, structlog base.
- [x] Fase 1: Dominio puro (Value Objects, NetworkFlow, DomainValidationError) con 23 tests en verde.
- [x] Fase 2: Capa de Aplicación - Puertos e Interfaces (Driving y Driven).
- [x] Fase 3: Infraestructura - Adaptador Zeek (Streaming asíncrono y Parsers TSV/JSON).
- [x] Fase 4: Caso de Uso - Normalizador Vectorial (Pandas/NumPy, IAT y doble salida).
- [ ] Fase 5: Infraestructura - Persistencia PostgreSQL (Esquema en Estrella y SQLAlchemy asíncrono).
- [ ] Fase 6: CLI y Entrypoints End-to-End.

## Especificación Fase 2 (Capa de Aplicación: Puertos)
1. **Driving Ports (`src/vortemis/application/ports/driving/`):**
   - `telemetry_source.py`: `TelemetrySourcePort` (Protocolo asíncrono con generador `stream() -> AsyncIterator[RawRecord]`).
   - `raw_record.py`: Tipo estructurado inmutable para la lectura cruda de líneas de logs.
2. **Driven Ports (`src/vortemis/application/ports/driven/`):**
   - `flow_repository.py`: `FlowRepositoryPort` (Protocolo asíncrono con método `save_batch(flows: list[NetworkFlow]) -> None`).
3. **Repositorio de Prueba (Falso/In-Memory):**
   - Implementar `InMemoryFlowRepository` en pruebas (`tests/doubles/in_memory_flow_repository.py`) para verificar que los puertos funcionen de forma aislada sin levantar Docker ni bases de datos todavía.


Usuarios, para atribuirles commits por requisitos de historial dinamico:
 Alias: Hector  User: DXpz Correo: antoniohector413@gmail.com      
 Alias: Alejandro User: Alejandro-svg-oss  Correo:     
 Alias: Mikel User: rorropirrorrobb  Correo:  michael.a.mancia.h@gmail.com   
 Alias: Fernando User: Pacic10s Correo:    fernandopalacios250@gmail.com
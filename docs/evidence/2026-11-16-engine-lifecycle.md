# Motor: ciclo de vida del engine

- Fecha: 2026-11-16
- Rama: `refactor/engine-lifecycle`
- Base: `develop` en `f3a7039`
- Objetivo: un solo dueño del engine de base de datos, sin crear y destruir un pool por consulta.

## 1. Problema anterior

`session_scope(database_url)` creaba un `AsyncEngine` en cada llamada y lo destruía al salir:

```python
@asynccontextmanager
async def session_scope(database_url: str) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(database_url)
    try:
        ...
    finally:
        await engine.dispose()
```

Consecuencias:

- Cada método de `SqlFlowQuery`, `SqlOperatorAuth` y `DatabaseTelemetryMaintenance` abría su propio pool.
- Un render del dashboard hacía entre tres y cinco llamadas: cinco engines y cinco pools.
- La configuración de conexión estaba repartida en varios adaptadores.
- No había un punto único para cerrar el engine.

## 2. Cambios

### `SqlDatabase`

`infrastructure/persistence/database.py`:

```python
class SqlDatabase:
    def __init__(self, url: str, pooling: bool = True) -> None: ...
    @property
    def engine(self) -> AsyncEngine: ...
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]: ...
    @property
    def dialect_name(self) -> str: ...
    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]: ...
    async def create_schema(self) -> None: ...
    async def dispose(self) -> None: ...
```

- `pooling=True` usa el pool por defecto; `pooling=False` usa `NullPool`.
- `create_schema` centraliza el `create_all` que antes estaba en el CLI.
- `dialect_name` evita que la purga tenga que abrir una conexión para decidir el SQL.

### Adaptadores

- `SqlFlowQuery(database)`, `SqlOperatorAuth(database)` y `DatabaseTelemetryMaintenance(database)` reciben el objeto, no una URL.
- `purge_telemetry(database, log_file)` usa `database.session()` y `database.dialect_name`.
- Se elimina `session.py`.

### Composition root

`build_telemetry_service(database, model_path)` recibe el `SqlDatabase` ya construido.

### Presentaciones y CLI

- Dashboard: un `@st.cache_resource` construye el servicio una vez por proceso con `pooling=False`.
- TUI: una instancia por app, con pool normal.
- CLI: un `SqlDatabase` para esquema, sesiones, repositorio y estado de ingesta; `dispose` en el `finally`.

### Por qué `NullPool` en presentaciones

Streamlit ejecuta cada operación con `asyncio.run`, es decir, un bucle de eventos nuevo por llamada. Una conexión de asyncpg cacheada en un pool queda atada al bucle anterior y falla al reutilizarse. Con `NullPool` cada operación abre y cierra su conexión dentro de su propio bucle, y el objeto `SqlDatabase` puede sobrevivir entre reruns.

La ingesta y la TUI, que viven en un único bucle, mantienen el pool normal.

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
156 passed in 13.25s
```

Tests nuevos:

- `tests/integration/test_database.py`: creación de esquema, sesiones consecutivas sobre el mismo engine, `NullPool` en modo presentación y pool por defecto en modo servidor.
- `tests/integration/test_flow_query.py` y `test_telemetry_maintenance.py`: usan `SqlDatabase` en lugar de URLs.

Prueba contra PostgreSQL real (`vortemis_lifecycle_check`, eliminada al terminar):

```text
migration=applied
loop1=[22, 443]
loop2=[445]
loop3_count=3
pooled_same_loop=3
lifecycle_check=ok
```

Lectura: tres `asyncio.run` separados reutilizan el mismo `SqlDatabase` con `NullPool`, y el modo con pool funciona dentro de un solo bucle.

## 4. Decisiones

- Un `SqlDatabase` por proceso, no uno por consulta.
- `NullPool` es obligatorio para presentaciones que hacen `asyncio.run` por operación.
- El pool normal queda para procesos con un único bucle: CLI, TUI, workers.
- El cierre es explícito donde hay un dueño claro (CLI, tests); en Streamlit lo gestiona el proceso.
- `create_schema` vive en el objeto de base de datos, no en el entrypoint.

## 5. Pendiente

1. Errores de aplicación tipados.
2. Agrupar las lecturas del dashboard en un solo `asyncio.run` por render.
3. Que el dashboard use filtros y `timeline` en lugar de 20 000 filas.
4. Retención y particionado de `fact_network_flows`.
5. Perfil SQLite/desktop con composition root propio.

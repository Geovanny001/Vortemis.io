# DECISIONS — Vortemis (log de decisiones de arquitectura)

Registro de decisiones tomadas para que cualquier agente/sesión nueva no las deshaga por desconocerlas.

## Stack y lenguaje
- **Python 3.14.6**: obligatorio por PEP 649 (evaluación diferida de anotaciones). No bajar a 3.12.
- **Docker usa `python:3.14-slim`**, no 3.12 (el código depende de 3.14).
- **`domain/` sin librerías externas**: solo stdlib. Pandas/NumPy/SQLAlchemy/PyTorch viven en application/infrastructure.

## Código
- **Cero comentarios `#`** en `.py`/`.sql`. Código autodocumentado por nombres + tipado.
- **Regla 7**: código, variables, métodos, endpoints, tablas, UI y commits 100% en inglés. El chat y la documentación de trabajo pueden ir en español.
- **ruff**: línea 100, reglas E,F,W,I,N,UP,B,C4,SIM,ASYNC,ANN (ANN desactivado en tests).
- **Sin docstrings** innecesarios.

## Persistencia
- **Esquema en estrella** PostgreSQL 16 + SQLAlchemy 2.x async + asyncpg.
- **`flow_id` se guarda como `String(36)`** (no tipo UUID), para compatibilidad SQLite/PostgreSQL.
- **Tests de integración** usan `sqlite+aiosqlite:///:memory:` con `poolclass=StaticPool` (no requieren PostgreSQL).
- **`create_all` no altera tablas existentes**: si cambia el esquema, hay que resetear el volumen (`docker compose down -v`).

## Seguridad / credenciales
- **Contraseñas**: SHA-256 + salt (`security.py`), no bcrypt/passlib.
- **GitHub (atribución de commits por equipo)**: usar email **noreply** (`{id}+{username}@users.noreply.github.com`) cuando no se tiene el email verificado. Alias del equipo en `OpenCode_context.md`.

## Datos de prueba
- `conn.log` / `conn_massive.log` deben ser **TSV con tabulaciones reales** y las 8 cabeceras Zeek.
- `seed_and_ingest` re-ingesta en cada `docker compose up` → duplica datos (pendiente de arreglar con `restart: "no"` o separando el seed).

## Mega upgrade (pendiente de confirmación)
- **Eliminar la capa REST** (`api.py`, `security.py`, `soc_users`, FastAPI/JWT) para volver a la arquitectura pura (Sección 0.4 del spec). DECISIÓN PENDIENTE del usuario.
- **PyTorch**: `TrafficAutoencoder` 6→16→3→16→6 (GELU+BatchNorm). Entrenar en GPU (RTX 5050, otra PC) con `scripts/train_gpu.py`; inferir en CPU (Docker) con el `.pt` exportado. Yo genero el código, el entrenamiento se hace fuera.
- **Umbral por defecto** `epsilon = 0.70`.
- **5 tácticas MITRE de red**: TA0010 (exfil), TA0008 (lateral), TA0040 (impact/DoS), TA0043 (recon), TA0011 (C2).

## Estabilización P0 de ingesta (2026-11-14)
- **Rama `release/p0-ingestion`** creada desde `develop` (`1e393c9`), no desde el tag `release/fase7` (`2616dec`), porque el tag es anterior a PyTorch, autenticación, TUI y sensor en vivo.
- **Evidencia**: cada cambio deja test, salida de `ruff`/`pytest`, prueba de runtime y un documento en `docs/evidence/`.
- **Identidad de commits de esta rama**: `DXpz <antoniohector413@gmail.com>`.
- **Checkpoint protegido**: `models/vortemis_ae.pt` no se sobrescribe ni se borra; los experimentos usan otra ruta y el reemplazo requiere aprobación.
- **Plan vigente**: `docs/IMPROVEMENT_PLAN.md`.
- **Puerta de calidad**: no se avanza sin `ruff check .` y `pytest` en verde.

## P1 calibración CICIDS2017 (2026-11-14)
- **Dataset**: CICIDS2017 `MachineLearningCSV` convertido a Parquet desde el mirror de Hugging Face; no se versiona.
- **Adaptador**: `scripts/prepare_cicids2017.py` mapea `Flow IAT Mean`, bytes, duración y flags a las 6 features.
- **Checkpoint original**: `models/vortemis_ae.pt` sigue intacto.
- **Checkpoint experimental**: `models/vortemis_ae_cicids.pt`, ignorado por Git y regenerable.
- **Umbral**: el selector `best_threshold` prioriza FPR ≤5% aunque el F1 baje; se corrigió el fallback que devolvía un umbral no compliant.
- **Resultado**: las 6 features tienen señal (AUC supervisado 0.998), pero el autoencoder actual solo llega a AUC 0.694; el autoencoder 6→32→8→32→6 sube a 0.868 y 56% de recall con FPR 5%.
- **Estado**: baseline completado. Las mejoras de modelo quedan como trabajo futuro; el foco actual es UI/ops.
- **Decisión pendiente**: autoencoder más grande + features de comportamiento, o modelo híbrido supervisado.

## UI/ops dashboard (2026-11-14)
- **Purga admin**: `TRUNCATE`/`DELETE` + rewrite del log con `ZEEK_CONN_HEADER`; solo rol `admin` y con confirmación.
- **Dashboard escribible en Docker**: el mount de `data/samples` deja de ser `:ro` para permitir la purga.
- **Estado del sensor**: se calcula por `mtime` del log; no se hardcodea “ACTIVE”.
- **Tests**: smoke tests de Streamlit con datos y estado vacío; test de integración de purga.
- **Validación**: `ruff` limpio y 99 tests verdes.

## Ops/seguridad (2026-11-14)
- **Rate limiting**: 5 intentos fallidos por usuario y bloqueo de 5 minutos; en memoria por proceso.
- **Credenciales**: operadores configurables con `VORTEMIS_*`; rotación con `scripts/set_operator_password.py`.
- **Healthcheck**: `scripts/healthcheck.py` y healthcheck del servicio `dashboard` en Compose.
- **TLS**: ejemplo `deploy/Caddyfile` y checklist en `docs/ops/SECURITY.md`.
- **Limitación**: el rate limiter debe moverse a Redis/PostgreSQL para múltiples réplicas.

## Separación UI/motor (2026-11-14)
- **Read side**: `TelemetryReadService` + `FlowQueryPort`, `OperatorAuthPort` y `TelemetryMaintenancePort`.
- **DTOs**: `FlowRecord` y `OperatorIdentity`; la UI no recibe modelos SQLAlchemy.
- **Adaptadores**: `SqlFlowQuery`, `SqlOperatorAuth` y `DatabaseTelemetryMaintenance`.
- **Composition root**: `entrypoints/container.py`.
- **Sin API REST**: las presentaciones usan el servicio directamente; el contrato queda listo para desktop o React.
- **Repositorio**: se mantiene en el mismo repo; monorepo vs repo separado se decide cuando el frontend sea real.

## Motor: identidad e idempotencia (2026-11-14)
- **Identidad**: `flow_fingerprint` en `domain/value_objects/`; uuid5 sobre `ts` (6 decimales), 5-tupla y protocolo.
- **Mapper**: asigna el `flow_id` determinista; no se usa `uuid4` en la ruta de ingesta.
- **Upsert**: `INSERT ... ON CONFLICT (flow_id) DO NOTHING` en PostgreSQL y SQLite. La idempotencia vive en la base de datos.
- **Contrato**: `FlowRepositoryPort.save_batch` devuelve el número de insertados y `FlowNormalizerUseCase.execute` lo agrega.
- **Índices**: `ts`, `src_ip`, `is_anomaly`, `anomaly_probability`, `tactic_id`.
- **Dimensiones**: caché por proceso; las tácticas son fijas y los protocolos y estados son estables.
- **Sin Alembic**: `create_all` no añade índices ni columnas a tablas existentes; las bases ya creadas requieren migración manual.
- **Datos previos**: los `flow_id` aleatorios existentes no se reescriben; una reingesta inserta una copia hasta purgar.

## Motor: estado de ingesta y migraciones (2026-11-14)
- **Estado**: tabla `ingestion_state` con una fila por `source_path`.
- **Identidad del archivo**: `device` e `inode`; si cambian, se reinicia el offset.
- **Reanudación**: si el tamaño es menor que el offset guardado, se empieza en 0.
- **Progreso**: `on_progress` se llama tras cada lote confirmado; el offset se escribe como máximo cada 5 segundos.
- **Corrección**: la idempotencia por `flow_id` sigue siendo la garantía; el offset solo evita reprocesar.
- **Purga**: borra `ingestion_state` porque el log se reescribe.
- **Migraciones**: Alembic con revisión `0001`; las bases creadas con `create_all` se adoptan con `alembic stamp head`.
- **Imagen Docker**: incluye `alembic.ini` y `migrations/` para migrar dentro del contenedor.

## Motor: contrato de consulta (2026-11-14)
- **Entrada**: `FlowFilters` valida zona horaria, ventana, puertos y probabilidad; normaliza protocolo y táctica.
- **Paginación**: keyset sobre `(ts, flow_id)`, cursor ISO 8601 más UUID; sin `OFFSET`.
- **Contrato**: `search_flows` devuelve `FlowPage`; `load_flows` se elimina para no mantener dos caminos.
- **Umbral**: `min_probability` sustituye al flag `is_anomaly`; el umbral es decisión de la presentación.
- **Agregaciones**: `top_sources` y `timeline` se calculan en SQL con `CASE` para anomalías.
- **Cubo temporal**: aritmética por dialecto (PostgreSQL `floor` + `extract`, SQLite `strftime` + truncado).
- **Zonas horarias**: el adaptador devuelve siempre `datetime` en UTC; SQLite pierde la zona al leer.
- **Consumidores**: dashboard y TUI se adaptan a `search_flows`; usar filtros en la UI queda pendiente.

## Motor: metadata del motor (2026-11-14)
- **DTO**: `ModelMetadata` con `architecture`, `feature_dim`, `tau`, `mean` y `std`; sin arrays de NumPy.
- **Puerto**: `EngineMetadataPort.load()` devuelve `None` si falta el checkpoint.
- **Adaptador**: `TorchEngineMetadata` deriva la arquitectura del `state_dict` y cachea por proceso.
- **Composition root**: recibe `model_path`; la presentación no resuelve el checkpoint.
- **Presentación**: el dashboard calcula z-scores con pandas y no importa NumPy ni `load_checkpoint`.
- **Pendiente**: `build_feature_vector` sigue en el módulo del modelo, así que el dashboard aún importa PyTorch de forma transitiva.

## Motor: features separadas del modelo (2026-11-16)
- **Módulo**: `application/features.py` con `FEATURE_DIM` y `build_feature_vector`; solo NumPy.
- **Modelo**: `bayesian_pytorch_engine.py` importa `FEATURE_DIM` y no reexporta el constructor de features.
- **Presentación**: el dashboard importa desde `application.features`; no carga PyTorch.
- **Clasificación**: `classify_mitre_tactic` se queda en el motor porque la ingesta ya carga el modelo.
- **Límite**: un test en subproceso verifica que `torch` no aparece en `sys.modules` al importar features.
- **Regla**: las features describen el vector, no la red; viven fuera del módulo de inferencia.

## Motor: ciclo de vida del engine (2026-11-16)
- **Dueño único**: `SqlDatabase` encapsula engine, session factory, dialecto, esquema y cierre.
- **Adaptadores**: reciben `SqlDatabase`, no una URL; no crean conexiones propias.
- **Presentaciones**: `NullPool` porque Streamlit ejecuta `asyncio.run` por operación y las conexiones no pueden cruzar bucles.
- **Procesos con un bucle**: CLI, TUI y workers mantienen el pool normal.
- **Esquema**: `create_schema` se mueve del entrypoint al objeto de base de datos.
- **Cierre**: explícito en CLI y tests; en Streamlit lo gestiona el proceso mediante `st.cache_resource`.
- **Eliminado**: `session.py`; no queda ningún engine por consulta.

## Convenciones de trabajo (2026-11-14)
- **Estándar de PR**: `docs/ops/PULL_REQUESTS.md` y plantilla `.github/pull_request_template.md`.
- **Un cambio lógico por PR**: código, tests, migración, documentación y evidencia en el mismo PR; no se abren PR de documentación separados.
- **Pull requests en inglés**: título `type: summary`, cuerpo y comentarios, incluidos los de documentación.
- **Releases en inglés**: tag kebab-case creado antes del PR y apuntando al head de la rama.
- **Validación previa**: `ruff check .` y `pytest` en verde, con la salida real en el cuerpo del PR.
- **Commits en inglés**: mensajes y nombres de archivo en inglés; la documentación interna puede seguir en español.
- **Sin emojis** en README, PR, releases ni documentación.
- **Merge**: merge commit, CI en verde y rama eliminada.

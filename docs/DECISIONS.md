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
- **Decisión pendiente**: autoencoder más grande + features de comportamiento, o modelo híbrido supervisado.

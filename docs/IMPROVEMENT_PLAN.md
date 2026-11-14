# Plan de mejoras — Vortemis.io

- Fecha: 2026-11-14
- Rama: `release/p0-ingestion`
- Base: `develop` en `1e393c9`
- Objetivo inmediato: estabilizar la ingesta P0 antes de calibrar el modelo o ampliar la UI.
- Alcance de esta rama: documentación, tests de regresión y fixes P0.
- Fuera de alcance por ahora: rediseño completo del dashboard, reentrenamiento del checkpoint y cambios de esquema.

## 1. Reglas del repositorio

Estas reglas son obligatorias y aplican a todo cambio:

| Regla | Referencia | Implicación |
|---|---|---|
| Arquitectura hexagonal estricta | `OpenCode_context.md` | `domain` no importa pandas, numpy, sqlalchemy, torch, textual ni streamlit |
| Python 3.14+ y tipado moderno | `OpenCode_context.md`, `docs/DECISIONS.md` | `list[T]`, `dict[K, V]`, `T \| None`, `Mapped[T]`, `mapped_column` |
| Cero comentarios `#` en `.py`/`.sql` | `OpenCode_context.md` | Código autodescriptivo, sin comentarios inline ni bloques |
| Ruff y pytest en verde | `OpenCode_context.md`, `docs/ROADMAP.md` | Ningún avance se considera terminado sin ambos comandos limpios |
| Código y commits en inglés | `OpenCode_context.md`, `docs/DECISIONS.md` | Variables, clases, archivos, UI y commits en inglés; chat y documentos en español |
| Branding `Vortemis.io` | `Context_Opencode(especificaciones1).md` | No usar “Vortemis” a secas ni “Vortemis SOC” en UI, banners, logs o README |
| Sin API REST intermedia | `Context_vortemis_puro.md` | No reintroducir FastAPI, Flask, JWT ni endpoints HTTP |
| Privacidad por diseño | `OpenCode_context.md` | Nunca persistir payload crudo; solo metadatos L3/L4 |
| Proteger el checkpoint | `Context_Opencode(especificaciones2).md` | `models/vortemis_ae.pt` no se sobrescribe ni se borra; los experimentos usan otra ruta y requieren aprobación para reemplazarlo |
| Evidencia por cambio | Este documento | Test en rojo, fix, ruff, pytest, prueba de runtime y commit convencional |

## 2. Protocolo de evidencias

Cada cambio debe dejar estos niveles:

| Nivel | Evidencia | Dónde queda |
|---|---|---|
| E1 | Test que reproduce el fallo y luego pasa | `tests/` |
| E2 | Salida de `ruff check .` y `pytest` | `docs/evidence/` y resumen del commit |
| E3 | Prueba de runtime: CLI, sensor, DB o dashboard | `docs/evidence/` |
| E4 | Commit convencional en inglés | Historial de Git |
| E5 | Documento de evidencia con antes/después | `docs/evidence/AAAA-MM-DD-tema.md` |

Plantilla mínima para E5:

```text
Problema:
Comando de reproducción:
Resultado antes:
Resultado después:
Tests añadidos:
Archivos tocados:
Riesgos residuales:
```

## 3. Flujo de trabajo

1. Crear una rama desde `develop`. Para este cambio: `release/p0-ingestion`.
2. Escribir primero el test que falla.
3. Implementar el fix mínimo.
4. Ejecutar `ruff check .` y `pytest`.
5. Probar el comportamiento real con PostgreSQL, CLI o dashboard.
6. Registrar la evidencia en `docs/evidence/`.
7. Hacer commits pequeños y convencionales.

Formato de commit observado en el historial:

```text
fix: prevent continuous mode from re-reading ingested log
fix: persist inter-arrival state across ingestion batches
test: cover continuous ingestion and iat regression
docs: record p0 ingestion evidence
```

## 4. Backlog priorizado

### P0 — Correctitud de ingesta y despliegue

| ID | Mejora | Archivos | Criterio de aceptación |
|---|---|---|---|
| P0-01 | Una sola fuente en modo continuo | `entrypoints/cli.py` | Reiniciar con un log lleno no crea facts nuevos; una línea nueva crea exactamente 1 |
| P0-02 | IAT con estado entre lotes | `application/use_cases/flow_normalizer.py` | El segundo flujo de una IP tiene IAT no nulo en modo continuo |
| P0-03 | Detectar truncado y rotación | `infrastructure/zeek/telemetry_source.py` | Truncar el log mientras se sigue no bloquea la ingesta |
| P0-04 | Timestamps y UDP correctos en el sensor | `infrastructure/zeek/live_sensor.py` | Cada flujo usa su propio timestamp; un flujo UDP se mapea correctamente |
| P0-05 | Modelo y continuo en Docker | `Dockerfile`, `docker-compose.yml` | La imagen contiene el checkpoint y el ingestor sigue vivo |
| P0-06 | Seed no destructivo | `scripts/seed_and_generate.py` | Ejecutar el seed dos veces no borra un log con datos |
| P0-07 | Checkpoint con carga segura | `bayesian_pytorch_engine.py`, `dashboard.py` | `weights_only=True` y validación de claves |
| P0-08 | Tests de regresión P0 | `tests/` | Los tests nuevos fallan antes y pasan después |

### P1 — Detección y calibración

| ID | Mejora | Criterio |
|---|---|---|
| P1-01 | Dataset etiquetado realista | Train/validación/test separados por tiempo y host |
| P1-02 | Recalibrar `mu`, `sigma`, `tau` y `epsilon` | Métricas por táctica y FPR acordado |
| P1-03 | Separar score del modelo y reglas MITRE | Una firma clara no depende de `P > epsilon` |
| P1-04 | Reescribir la regla C2 | HTTPS normal no se etiqueta como C2 |
| P1-05 | Evaluación reproducible | Script y snapshot de calibración |

### P2 — Datos y rendimiento

| ID | Mejora | Criterio |
|---|---|---|
| P2-01 | Deduplicación determinista | Reingerir el mismo log produce 0 facts nuevos |
| P2-02 | Alembic | Migración desde cero y upgrade probados |
| P2-03 | Índices y retención | Consultas del dashboard <500 ms con 1M filas |
| P2-04 | Micro-lotes y caché de dimensiones | Sin 3 SELECT y commit por flujo |

### P3 — Seguridad y operación

| ID | Mejora | Criterio |
|---|---|---|
| P3-01 | Secretos fuera del código | Sin credenciales ni tokens en el repo |
| P3-02 | Auth endurecida | Rate limiting, bloqueo y sesión con expiración |
| P3-03 | TLS/reverse proxy | Dashboard no expuesto en HTTP plano |
| P3-04 | CI | Ruff, pytest y build de Docker en GitHub Actions |
| P3-05 | Logging y métricas | Flujos/s, latencia, errores y última ingesta |

### P4 — Producto

| ID | Mejora | Criterio |
|---|---|---|
| P4-01 | Dashboard: purga, estado vacío, filtros y caché | Admin purga; analyst no puede; refresh no bloquea |
| P4-02 | TUI: columnas reales y KPIs coherentes | `State` real y KPIs sobre el mismo alcance |

### P5 — Documentación

| ID | Mejora | Criterio |
|---|---|---|
| P5-01 | Reconciliar README, ROADMAP, DECISIONS y traspaso | Documentación coincide con el repo |
| P5-02 | Limpiar artefactos obsoletos | Sin Postman de una API eliminada |

## 5. Cronograma sugerido

| Semana | Entregable |
|---|---|
| 1 | Fase 0 + P0: ingesta estable, tests de regresión, Docker con modelo |
| 2 | P1: dataset etiquetado, métricas y calibración inicial |
| 3 | P2 + P3: dedup, migraciones, índices, CI y seguridad |
| 4 | P4 + P5: dashboard/TUI y documentación final |

## 6. Métricas de éxito

- 0 duplicados al reiniciar o reingerir.
- IAT no nulo salvo el primer flujo por IP.
- Las 5 tácticas se disparan en pruebas controladas.
- FPR ≤5% sobre tráfico normal de laboratorio.
- 80+ tests verdes y ruff limpio.
- CI verde.
- Imagen Docker con checkpoint y `tau` visible.
- Sin credenciales ni tokens en el repo.

## 7. Riesgos y no objetivos

- La calibración real depende de conseguir tráfico etiquetado; sin eso, el sistema queda como demo.
- Docker y `tshark` en Windows pueden requerir permisos de administrador.
- No se añadirán nuevas tácticas MITRE hasta estabilizar las 5 actuales.
- No se reentrenará `models/vortemis_ae.pt` sin aprobación explícita.

## 8. Primer sprint

1. Tests de regresión de P0-01 y P0-02 en rojo.
2. Fix de doble ingesta y estado de IAT.
3. Ruff, pytest y prueba de runtime.
4. Evidencia en `docs/evidence/2026-11-14-p0-ingestion.md`.
5. Repetir con P0-03 a P0-06.

## 9. Referencias

- `OpenCode_context.md`
- `Context_vortemis_puro.md`
- `Context_Opencode(especificaciones1).md`
- `Context_Opencode(especificaciones2).md`
- `docs/DECISIONS.md`
- `docs/ROADMAP.md`
- `docs/evidence/2026-11-14-p0-ingestion.md`

## 10. Estado de implementación

- [x] P0-01: una sola lectura del log en modo continuo.
- [x] P0-02: IAT persistente entre lotes.
- [x] P0-03: truncado y rotación del log.
- [x] P0-04: timestamps y puertos UDP del sensor.
- [ ] P0-05: Docker con modelo y modo continuo.
- [ ] P0-06: seed no destructivo.
- [ ] P0-07: carga segura del checkpoint.
- [ ] P0-08: suite de regresión completa.

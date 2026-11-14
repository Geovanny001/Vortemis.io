# Estándar de pull requests

- Ámbito: todos los cambios del repositorio, incluidos documentación, CI y scripts.
- Plantilla: `.github/pull_request_template.md` (GitHub la carga automáticamente).
- Idioma: título, cuerpo, comentarios de revisión y notas de release en inglés. La documentación interna sigue en español.
- Emojis: prohibidos.

## 1. Principios

1. **Un PR, un cambio lógico.** Si el título necesita un "y", son dos PR.
2. **Todo dentro del mismo PR.** Código, tests, migración, documentación y evidencia viajan juntos. No se abre un PR de documentación para un cambio de código.
3. **El PR se puede revisar sin abrir el diff completo.** El cuerpo explica qué, por qué y cómo se comprobó.
4. **La validación es reproducible.** Cada afirmación del PR tiene un comando y una salida real.
5. **El release existe antes del PR.** El tag apunta al commit que se va a fusionar.

## 2. Título

Formato:

```text
<type>: <summary>
```

- `type` es uno de: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `ci`, `chore`, `build`.
- `summary` va en imperativo, en minúscula y sin punto final.
- Longitud máxima: 72 caracteres.
- Sin emojis, sin números de ticket al principio y sin "WIP".
- El scope entre paréntesis solo si aporta: `fix(ingestion): ...`.

Expresión de validación:

```text
^(feat|fix|refactor|perf|test|docs|ci|chore|build)(\([a-z0-9-]+\))?: [a-z][^.]{0,60}$
```

Ejemplos del repositorio que cumplen el formato:

- `fix: stabilize p0 ingestion, sensor and deployment`
- `refactor: separate ui from telemetry read service`
- `feat: make flow ingestion idempotent and index the fact table`

## 3. Cuerpo

Se copia la plantilla y se rellenan todas las secciones en este orden. Si una no aplica, se escribe `None`; no se borra.

| Sección | Contenido obligatorio |
|---|---|
| `Summary` | Qué cambia y qué fallo, hueco o riesgo cierra. Un párrafo. |
| `Closes` | `Closes: #N` o `Closes: none`. |
| `Type` | Una casilla marcada. Coincide con el prefijo del título. |
| `Context` | Comportamiento actual y evidencia: test que falla, cifras medidas, incidente. |
| `Changes` | Tabla por capa: domain, application, infrastructure, entrypoints, tests, docs. |
| `Contract impact` | Puertos, DTOs, esquema, migración, configuración y comportamiento público. |
| `Validation` | Comandos literales y su salida. Enlace al archivo de evidencia. |
| `Data impact` | Filas existentes, reingesta, purga o backfill. |
| `Risk and rollback` | Qué puede romperse y cómo se revierte. |
| `Release` | Tag y URL del release. |
| `Checklist` | Marcada antes de pedir revisión. |

Reglas de redacción:

- Frases cortas y verificables. Nada de "varios arreglos" ni "mejoras".
- Las cifras se escriben con su contexto: `117 passed in 10.90s`.
- No se pega salida inventada ni resumida: se copia la real.
- Los cambios de UI incluyen captura antes/después, como en Airflow.
- Los cambios de datos indican si hace falta purgar o reingerir.

## 4. Tamaño y división

- Objetivo: menos de 600 líneas modificadas y menos de 20 archivos.
- Si se supera, se justifica en `Context` o se divide.
- Un PR no mezcla refactor y cambio de comportamiento. Primero el refactor, después el cambio.
- Un PR no toca más de dos capas sin justificarlo.
- Las migraciones van en el mismo PR que el cambio de esquema, nunca después.

## 5. Validación y evidencia

Comandos mínimos, siempre en el mismo orden:

```text
python -m uv run ruff check .
python -m uv run pytest
```

- Se añade una comprobación de runtime cuando el cambio lo permite: base de datos real, CLI, sensor, dashboard o contenedor.
- La evidencia vive en `docs/evidence/YYYY-MM-DD-<slug>.md` con problema, cambios, validación, decisiones y pendiente.
- `docs/ROADMAP.md` recibe la entrada del cambio y enlaza la evidencia.
- `docs/DECISIONS.md` recibe la decisión si el cambio crea una regla que no debe deshacerse.

## 6. Release

- Un release por PR, creado **antes** de abrir el PR.
- Nombre del tag: kebab-case con área y cambio, por ejemplo `engine-idempotent-ingestion`, `ui-engine-separation`, `p0-07-safe-checkpoint`.
- El tag apunta al head de la rama. Si el PR recibe commits después, se mueve el tag antes del merge.
- Las notas del release van en inglés y resumen cambios, resultado y validación.
- El cuerpo del PR enlaza el tag y la URL del release.

## 7. Revisión y merge

- CI en verde antes del merge.
- Estrategia de merge: merge commit, como el historial actual (`Merge pull request #N from ...`).
- Rama eliminada tras el merge.
- Sin force-push después de una revisión; el rebase se hace antes.
- El merge lo hace quien revisa, no quien abre el PR, salvo que sea el mismo operador.

## 8. Prohibiciones

- PR con varios cambios lógicos.
- PR de documentación separado de su cambio.
- Cuerpo en español, con emojis o con secciones vacías.
- Verificación sin salida real.
- Tocar `models/vortemis_ae.pt`.
- Secretos, tokens o rutas locales en el diff.
- Comentarios `#` en archivos Python o SQL.

## 9. Referencias

Patrones tomados de proyectos abiertos y de nuestro propio historial:

| Fuente | Qué se adopta |
|---|---|
| Kubernetes | Tipo de cambio explícito, bloque de release note y notas para el revisor. |
| Apache Airflow | Enlace a issue con `closes`/`related` y capturas para cambios de UI. |
| OpenTelemetry | Secciones separadas de `Testing` y `Documentation`. |
| Rust | Política explícita de uso de LLM; en Vortemis queda como divulgación opcional por ahora. |
| PR #10–#17 de Vortemis.io | Estructura `Summary` + `Validation` + `Notes`, que ya funcionó y se conserva. |

## 10. Checklist rápido

- [ ] Un cambio lógico y todo su material en el mismo PR.
- [ ] Título `type: summary`, inglés, 72 caracteres.
- [ ] Cuerpo con la plantilla completa y `None` donde no aplique.
- [ ] Salida real de `ruff` y `pytest`.
- [ ] Evidencia en `docs/evidence/` y entrada en `docs/ROADMAP.md`.
- [ ] Release creado y enlazado.
- [ ] Sin emojis y sin secretos.

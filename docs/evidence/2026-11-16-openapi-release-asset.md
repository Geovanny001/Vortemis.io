# OpenAPI como activo del release

- Fecha: 2026-11-16
- Rama: `ci/openapi-release-asset`
- Base: `develop` en `de28cca`
- Objetivo: que cada release publique `openapi.json` como descarga.

## 1. Problema anterior

El contrato se exportaba en el CI del PR como artefacto del run, pero el release de GitHub no lo incluía. Un frontend que fija una versión tenía que sacarlo de un run concreto.

## 2. Cambios

- Nuevo workflow `openapi-release.yml` con `on: release: types: [published]`.
- Instala uv, sincroniza dependencias, ejecuta `scripts/export_openapi.py`.
- Sube `docs/openapi.json` al release con `gh release upload ... --clobber`.
- Permiso `contents: write` limitado al workflow.

```text
on:
  release:
    types: [published]
```

## 3. Validación

```text
$ python -m uv run ruff check .
All checks passed!

$ python -m uv run pytest
193 passed in 27.98s
```

Comprobación estática: `tests/test_deployment.py` verifica que el workflow existe, escucha `release` y sube `docs/openapi.json`.

El workflow solo se ejecuta en un release publicado, así que su primera ejecución real será el próximo release.

## 4. Decisiones

- Se usa el archivo versionado del repo, no una instancia en ejecución.
- `--clobber` permite republicar el mismo tag sin fallar.
- El activo se genera en el runner con las dependencias del proyecto, igual que en el CI.
- No se ejecuta en cada push: solo cuando se publica un release.

## 5. Pendiente

1. Verificar la primera ejecución real del workflow.
2. Adjuntar también un `CHANGELOG` o notas firmadas, si se decide.

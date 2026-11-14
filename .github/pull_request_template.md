<!--
Vortemis.io pull request template.

Rules: docs/ops/PULL_REQUESTS.md
Write in English. No emojis. Keep every section; write "None" when it does not apply.
Delete the HTML comments before opening the pull request.
-->

## Summary

<!-- One paragraph: what changes and which failure mode, gap or risk it closes. -->

Closes: none

## Type

- [ ] feat
- [ ] fix
- [ ] refactor
- [ ] perf
- [ ] test
- [ ] docs
- [ ] ci
- [ ] chore

## Context

<!-- Current behaviour and evidence: failing test, measured numbers, incident or missing capability. -->

## Changes

| Layer | Change |
|---|---|
| Domain | None |
| Application | None |
| Infrastructure | None |
| Entrypoints | None |
| Tests | None |
| Docs | None |

## Contract impact

- Ports and DTOs: None
- Database schema: None
- Migration required: None
- Configuration or environment: None
- Public behaviour: None

## Validation

```text
$ python -m uv run ruff check .
$ python -m uv run pytest
```

<!-- Paste the real output. Add runtime checks with their observed values. -->

Evidence: `docs/evidence/YYYY-MM-DD-<change>.md`

## Data impact

- Existing rows: None
- Re-ingestion: None
- Purge or backfill: None

## Risk and rollback

- Risk: None
- Rollback: None

## Release

- Tag: `<area>-<change>`
- URL: None

## Checklist

- [ ] One logical change: code, tests, docs and evidence in this pull request
- [ ] Title follows `<type>: <summary>`, imperative and at most 72 characters
- [ ] Body and release notes are in English, with no emojis
- [ ] Hexagonal boundaries respected
- [ ] No `#` comments in Python or SQL source files
- [ ] `models/vortemis_ae.pt` untouched
- [ ] `ruff check .` and `pytest` green, output pasted above
- [ ] Evidence file added and linked from `docs/ROADMAP.md`
- [ ] Release tag created before opening the pull request and pointing at the head commit

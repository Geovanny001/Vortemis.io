import json
from pathlib import Path

from vortemis.entrypoints.api import app

_DOCUMENT = Path("docs/openapi.json")


def test_committed_openapi_matches_the_app() -> None:
    committed = json.loads(_DOCUMENT.read_text(encoding="utf-8"))

    assert committed == app.openapi()


def test_openapi_documents_the_api_surface() -> None:
    schema = app.openapi()

    assert "/v1/auth/refresh" in schema["paths"]
    assert "/v1/admin/purge" in schema["paths"]
    assert "/v1/stats/timeline" in schema["paths"]

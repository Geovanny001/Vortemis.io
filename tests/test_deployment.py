from pathlib import Path


def test_dockerfile_copies_model_checkpoint() -> None:
    content = Path("Dockerfile").read_text(encoding="utf-8")

    assert "COPY models" in content
    assert "MODEL_PATH" in content


def test_dockerfile_installs_torch_before_source() -> None:
    content = Path("Dockerfile").read_text(encoding="utf-8")

    assert content.index("torch") < content.index("COPY src")


def test_compose_enables_continuous_ingestion() -> None:
    content = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert 'CONTINUOUS_MODE: "true"' in content
    assert "MODEL_PATH" in content


def test_dockerignore_does_not_exclude_models() -> None:
    content = Path(".dockerignore").read_text(encoding="utf-8")

    assert "models" not in content


def test_compose_exposes_the_api_service() -> None:
    content = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "uvicorn vortemis.entrypoints.api:app" in content
    assert '"8000:8000"' in content
    assert "HEALTHCHECK_URL: http://127.0.0.1:8000/v1/health" in content


def test_ci_uploads_the_openapi_artifact() -> None:
    content = Path(".github/workflows/docker-build.yml").read_text(
        encoding="utf-8"
    )

    assert "scripts/export_openapi.py" in content
    assert "actions/upload-artifact@v4" in content


def test_release_workflow_attaches_the_openapi_artifact() -> None:
    content = Path(".github/workflows/openapi-release.yml").read_text(
        encoding="utf-8"
    )

    assert "release:" in content
    assert "gh release upload" in content
    assert "docs/openapi.json" in content

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

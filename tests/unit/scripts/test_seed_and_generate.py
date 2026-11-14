from pathlib import Path

from scripts import seed_and_generate


async def _noop_seed_database() -> None:
    return None


async def test_seed_creates_header_only_log(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "conn_massive.log"
    monkeypatch.setattr(seed_and_generate, "SAMPLE_PATH", log_path)
    monkeypatch.setattr(seed_and_generate, "seed_database", _noop_seed_database)

    await seed_and_generate._run()

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8
    assert lines[0].startswith("#separator")


async def test_seed_preserves_existing_log(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "conn_massive.log"
    log_path.write_text("existing\n", encoding="utf-8")
    monkeypatch.setattr(seed_and_generate, "SAMPLE_PATH", log_path)
    monkeypatch.setattr(seed_and_generate, "seed_database", _noop_seed_database)

    await seed_and_generate._run()

    assert log_path.read_text(encoding="utf-8") == "existing\n"


async def test_generate_sample_requires_force_to_overwrite(
    tmp_path: Path, monkeypatch
) -> None:
    log_path = tmp_path / "conn_massive.log"
    log_path.write_text("existing\n", encoding="utf-8")
    monkeypatch.setattr(seed_and_generate, "SAMPLE_PATH", log_path)
    monkeypatch.setattr(seed_and_generate, "seed_database", _noop_seed_database)

    await seed_and_generate._run(generate_sample=True)
    assert log_path.read_text(encoding="utf-8") == "existing\n"

    await seed_and_generate._run(generate_sample=True, force=True)

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 5008

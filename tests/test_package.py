import importlib


def test_hexagonal_packages_are_importable() -> None:
    for module in (
        "vortemis.domain",
        "vortemis.application",
        "vortemis.infrastructure",
        "vortemis.entrypoints",
    ):
        importlib.import_module(module)

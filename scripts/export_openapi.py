import json
from pathlib import Path

from vortemis.entrypoints.api import app

TARGET = Path(__file__).resolve().parents[1] / "docs" / "openapi.json"


def main() -> None:
    document = app.openapi()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(TARGET)


if __name__ == "__main__":
    main()

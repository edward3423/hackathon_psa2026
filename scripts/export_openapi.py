import json
from pathlib import Path

from cascade.api import app


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "contracts" / "openapi.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()

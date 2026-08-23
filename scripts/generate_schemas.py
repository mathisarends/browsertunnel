import json
from pathlib import Path

from backend.presentation.schemas import (
    browser_json_schema,
    browser_openrpc_schema,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = PROJECT_ROOT / "schemas"


def main() -> None:
    SCHEMA_DIR.mkdir(parents=True, exist_ok=True)

    schemas = {
        "schema.json": browser_json_schema(),
        "openrpc.json": browser_openrpc_schema(),
    }
    for filename, document in schemas.items():
        path = SCHEMA_DIR / filename
        path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Generated {path.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()

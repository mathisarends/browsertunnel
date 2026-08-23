import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from scripts.typescript_codegen import (
    TypeScriptClientOptions,
    write_typescript_client,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA = PROJECT_ROOT / "schemas" / "openrpc.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "packages" / "browser-rpc-client" / "src" / "generated"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the BrowserTunnel TypeScript RPC client."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)

    document = json.loads(arguments.schema.read_text(encoding="utf-8"))
    changed = write_typescript_client(
        document,
        arguments.output,
        TypeScriptClientOptions(
            client_name="BrowserTunnelClient",
            source=arguments.schema.name,
        ),
        check=arguments.check,
    )
    for path in changed:
        label = "Out of date" if arguments.check else "Wrote"
        print(f"{label}: {path.relative_to(PROJECT_ROOT)}")
    if not changed:
        print("TypeScript RPC client is up to date")
    return int(arguments.check and bool(changed))


if __name__ == "__main__":
    raise SystemExit(main())

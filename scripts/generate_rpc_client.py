"""Generate with the pinned upstream generator; rpcgen.toml owns the contract."""

import sys

from fastapi_rpckit.codegen.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["generate", "--config", "rpcgen.toml", *sys.argv[1:]]))

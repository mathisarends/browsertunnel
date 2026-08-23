#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "Fehler: 'uv' ist nicht installiert oder nicht im PATH." >&2
  exit 1
fi

exec uv run python -m scripts.generate_schemas

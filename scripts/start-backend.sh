#!/usr/bin/env sh
set -eu

# Immer vom Projektverzeichnis aus starten, egal von wo das Skript aufgerufen wird.
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "Fehler: 'uv' ist nicht installiert oder nicht im PATH." >&2
  echo "Installation: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

if [ ! -f .env ] && [ -f .env.example ]; then
  echo "Keine .env gefunden – verwende die Standardwerte aus .env.example."
  cp .env.example .env
fi

export RELOAD="${RELOAD:-1}"

echo "Backend wird auf http://localhost:${PORT:-8000} gestartet ..."
exec uv run python -m backend.main

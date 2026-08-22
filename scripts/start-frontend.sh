#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -x node_modules/.bin/vite ]; then
  echo "Installing frontend dependencies..."
  npm install
fi

exec npm run dev

# BrowserTunnel

Minimaler Frontend-Scaffold für einen Browser-Stream: TypeScript mit einem
zentrierten Canvas (intern 1920 × 1080 Pixel).

## Setup

```bash
uv sync
npm install
uv run pre-commit install
```

## Development

```bash
# Frontend starten (installiert fehlende Pakete automatisch)
sh scripts/start-frontend.sh

# Danach im Browser öffnen: http://localhost:5173

uv run pytest        # tests
uv run ruff check .  # lint
uv run ruff format . # format
npm run build        # TypeScript prüfen und Frontend bauen
```

Alternativ kann das Frontend nach `npm install` direkt mit `npm run dev`
gestartet werden. Der Vite-Entwicklungsserver aktualisiert die Seite bei
Änderungen an HTML, CSS oder TypeScript automatisch (Hot Reload).

Vite leitet im Entwicklungsmodus alle Aufrufe unter `/api` an das separat
laufende Backend auf Port 8000 weiter. Der Einstiegspunkt für den späteren
Framecast-Renderer ist `drawFrame()` in `frontend/src/main.ts`; für API-Aufrufe
steht `getJson()` in `frontend/src/api.ts` bereit.

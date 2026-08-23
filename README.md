# BrowserTunnel

Minimaler Frontend-Scaffold für einen Browser-Stream: TypeScript mit einer
Browser-Vorschau (intern 1600 × 900 Pixel), URL-Leiste und Event-Log für das
Debugging der Frontend-/Backend-Kommunikation. Die Tab-Leiste unterstützt das
Erstellen, Wechseln und Schließen mehrerer lokaler Browser-Tabs.

## Setup

```bash
uv sync
npm install
uv run pre-commit install
```

## Development

```bash
# Backend starten (richtet Abhängigkeiten und .env bei Bedarf ein)
sh scripts/start-backend.sh

# Frontend starten (installiert fehlende Pakete automatisch)
sh scripts/start-frontend.sh

# Danach im Browser öffnen: http://localhost:5173

sh scripts/generate-schemas.sh # JSON-Schema und OpenRPC nach schemas/ schreiben
npm run generate:rpc # Schemas und TypeScript-RPC-Client neu generieren
uv run pytest        # tests
uv run ruff check .  # lint
uv run ruff format . # format
npm run build        # TypeScript prüfen und Frontend bauen
```

Alternativ kann das Frontend nach `npm install` direkt mit `npm run dev`
gestartet werden. Vor jedem Start erzeugt `predev` automatisch die aktuellen
Schemas aus dem Backend und generiert daraus den TypeScript-RPC-Client. Der
Vite-Entwicklungsserver aktualisiert die Seite bei Änderungen an HTML, CSS oder
TypeScript automatisch (Hot Reload).

Vite leitet im Entwicklungsmodus alle Aufrufe unter `/api` an das separat
laufende Backend auf Port 8000 weiter. Der statisch aus OpenRPC generierte Client
ist das eigene npm-Workspace-Package `packages/browser-rpc-client`. Der Generator
lebt vorerst unter `scripts/`; `npm run check:generated` erkennt veraltete
generierte Dateien.

## Backend-Protokoll

Der POC hat genau einen fachlichen WebSocket-Router. Alle Client-Befehle laufen
als JSON-RPC 2.0 über:

- WebSocket: `ws://127.0.0.1:8000/api/browser/ws`
- vollständiges JSON Schema: `/api/browser/schema.json`
- OpenRPC für Client-Generierung: `/api/browser/openrpc.json`

Beispiel:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "browser.nav.navigate",
  "params": {"url": "https://example.com"}
}
```

Browserereignisse sendet der Server als JSON-RPC-Notification `browser.event`.
`params.type` unterscheidet Frames, Tab- und Navigationszustand sowie abgestürzte
oder getrennte Targets. Frames sind im Application-Layer JPEG-Bytes und werden
nur für den JSON-Transport als Base64 kodiert. Die dekorierten `pyrpckit`-Methoden
decken URL-Navigation, Zurück, Vor, Neuladen, Ladestopp, getrennte Click- und
Hover-Eingaben, Scrollen,
Tastatur, Texteingabe, Clipboard sowie Tab-Liste, -Erstellung, -Aktivierung und
-Schließen ab.

Der Browser lässt sich mit `BROWSER_EXECUTABLE`, `BROWSER_CDP_URL`,
`BROWSER_HEADLESS`, `BROWSER_WIDTH`, `BROWSER_HEIGHT`,
`BROWSER_SCREENCAST_QUALITY` und `BROWSER_STARTUP_TIMEOUT` konfigurieren. Ohne
`BROWSER_CDP_URL` startet das Backend selbst Chrome, Chromium oder Edge.

Ein realer Adapter-Smoke-Test steht über
`uv run python -m scripts.smoke_backend` bereit. V1 hat noch keine
Authentifizierung; den Tunnel deshalb nur lokal oder hinter einem
authentifizierenden Reverse Proxy bereitstellen.

# BrowserTunnel

Mirrors a real Chromium tab into a web page. The backend drives the tab over
the Chrome DevTools Protocol, streams its frames to a `<canvas>`, and replays
the viewer's mouse, keyboard, scroll, and clipboard actions back onto it.
Feels like a remote desktop for one tab, but it's just JSON-RPC over a
WebSocket — no video codec involved.

## Architecture

```
┌──────────────────────┐   single WebSocket, JSON-RPC 2.0    ┌───────────────────────────┐
│       Frontend        │ ──────────────────────────────────▶ │          Backend           │
│  (TypeScript, Vite)   │  requests: navigate, mouse, key...  │  BrowserSession             │
│                        │ ◀────────────────────────────────  │  Browser (nav · input ·    │
│  <canvas> viewport     │  frames, tab/nav/cursor state       │  clipboard · tabs)         │
└────────────────────────┘                                    └─────────────┬──────────────┘
                                                                              │
                                                                       Chrome DevTools
                                                                          Protocol
                                                                              │
                                                                    ┌─────────▼─────────┐
                                                                    │ Chromium / Chrome  │
                                                                    │ (headless or not)  │
                                                                    └────────────────────┘
```

**Rendering.** The tab's screencast is pushed frame by frame as JSON-RPC
notifications and drawn onto a 1600×900 canvas. No iframe, no embedded
browser engine, no cross-origin headaches — just a fast-moving image.

**Input is imitated, not embedded.** The tab only exists on the server. Every
click, drag, scroll, and keystroke the user does on the canvas becomes a DOM
event, gets translated into a CDP input command, and gets replayed on the
mirrored tab. To the tab, that input looks exactly like it came from a real
user — which is what makes this work on arbitrary sites without any
per-site integration.

**Layering.** `backend/application` defines what a browser can do
(`navigation`, `input`, `clipboard`, `tabs`); `backend/infrastructure/cdp_browser`
implements that over CDP; `backend/presentation` exposes it as JSON-RPC and
owns the WebSocket session. Swapping the CDP adapter, or the RPC transport,
shouldn't touch the other two.

**One socket, both directions at once.** Requests (`browser.nav.*`,
`browser.input.*`, ...) go one way; a `browser.event` notification stream
(tab/navigation/cursor state, crashes, detach) and the frame stream go the
other, both running as background tasks for as long as the connection is
open.

**Why this exists.** This is a learning project, not a hardened product —
there's no auth on the WebSocket, no rate limiting, none of the things a
real deployment would need. Treat it as a reference for the core idea: how
you'd mirror and control a browser tab remotely, stripped down to that one
concept.

The JSON-RPC plumbing and the CDP client are pulled in as libraries
(`pyrpckit`, `cdpify`), not written here — the interesting part is how the
tab is mirrored and controlled, not the wire format.

## Setup

```bash
uv sync
npm install
uv run pre-commit install
```

## Development

```bash
# Start the backend (sets up dependencies and .env on demand)
sh scripts/start-backend.sh

# Start the frontend (installs missing packages automatically)
sh scripts/start-frontend.sh

# Then open in a browser: http://localhost:5173

sh scripts/generate-schemas.sh # write JSON Schema and OpenRPC into schemas/
npm run generate:rpc # regenerate schemas and the TypeScript RPC client
uv run pytest        # tests
uv run ruff check .  # lint
uv run ruff format . # format
npm run build        # type-check and build the frontend
```

The frontend can also just be started with `npm run dev` after `npm install`
— `predev` regenerates schemas and the RPC client first. Vite hot-reloads on
HTML/CSS/TS changes and proxies `/api` to the backend on port 8000. The
generated client lives in the workspace package
`packages/browser-rpc-client`; `npm run check:generated` flags a stale one.

## Backend protocol

One WebSocket, JSON-RPC 2.0:

- `ws://127.0.0.1:8000/api/browser/ws`
- JSON Schema: `/api/browser/schema.json`
- OpenRPC: `/api/browser/openrpc.json`

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "browser.nav.navigate",
  "params": { "url": "https://example.com" }
}
```

Server-pushed events arrive as `browser.event`; `params.type` tells frames
apart from tab/navigation state and crashed/detached targets. Frames are
JPEG, base64-encoded for the JSON transport. Methods cover navigation
(back/forward/reload/stop), mouse/scroll/keyboard input, clipboard, and tab
list/create/activate/close.

Configure the browser via `BROWSER_EXECUTABLE`, `BROWSER_CDP_URL`,
`BROWSER_HEADLESS`, `BROWSER_WIDTH`, `BROWSER_HEIGHT`,
`BROWSER_SCREENCAST_QUALITY`, `BROWSER_STARTUP_TIMEOUT`. Without
`BROWSER_CDP_URL` the backend launches Chrome/Chromium/Edge itself.

Smoke test against a real browser: `uv run python -m scripts.smoke_backend`.

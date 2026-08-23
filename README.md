# BrowserTunnel

BrowserTunnel mirrors a real, headful-capable Chromium tab into a web page. A
FastAPI backend drives an actual browser over the Chrome DevTools Protocol
(CDP), streams its rendered frames to a `<canvas>` in the client, and replays
the viewer's mouse, keyboard, scroll, and clipboard actions on that tab as if
they happened locally. The result behaves like a remote desktop for a single
browser tab, but is implemented as a thin JSON-RPC protocol over one
WebSocket rather than a video codec.

## Architecture

```
┌─────────────────────┐        single WebSocket, JSON-RPC 2.0        ┌───────────────────────────┐
│       Frontend       │ ───────────────────────────────────────────▶ │          Backend           │
│  (TypeScript, Vite)  │   requests: navigate, mouse, key, tabs...    │   (FastAPI + pyrpckit)      │
│                       │ ◀─────────────────────────────────────────── │                             │
│  <canvas> viewport    │   notifications: frames, tab/nav/cursor     │  CDP session (cdpify)        │
└───────────────────────┘   state, target crashed/detached           └──────────────┬──────────────┘
                                                                                       │
                                                                              Chrome DevTools Protocol
                                                                                       │
                                                                              ┌────────▼────────┐
                                                                              │ Chromium / Chrome │
                                                                              │  (headless or not)│
                                                                              └───────────────────┘
```

**Canvas rendering.** The backend enables CDP's `Page.startScreencast` on the
active tab and pushes each captured frame to the client as a JSON-RPC
notification. The frontend decodes the JPEG and draws it onto an
1600×900 `<canvas>`, so the "browser" the user sees is just a video feed of
frames blitted at animation-frame rate — no iframe, no embedded browser
engine, no cross-origin restrictions.

**Events imitated, not embedded.** The tab lives entirely on the server; the
client never touches it directly. Every pointer move, click, drag, scroll,
keystroke, and clipboard action the user performs on the canvas is captured
as a DOM event, translated into a CDP `Input.dispatch*` call, and replayed
against the mirrored tab. From the tab's point of view, an input event
arrived that is indistinguishable from a real one. This is what makes the
tunnel general-purpose: it doesn't need per-site integration, only a faithful
mapping from browser-native input events to CDP input events (including
held-button drags and IME-safe text insertion).

**FastAPI backend.** `backend/app.py` wires a single FastAPI app with one
WebSocket route (`backend/presentation/router.py`) and a Dishka DI container
that provides the `Browser` application port and a per-connection
`BrowserSession`. The layering follows a small ports-and-adapters split:

- `backend/application` — the `Browser` protocol, grouped into
  `navigation`, `input`, `clipboard`, and `tabs` namespaces, plus the
  `BrowserEvent` union the tab reports back.
- `backend/infrastructure/cdp_browser` — the CDP-backed implementation
  (`CdpBrowser`) built on top of `cdpify`, translating protocol calls into
  CDP domain calls and CDP events into `BrowserEvent`s.
- `backend/presentation` — the JSON-RPC surface (`pyrpckit`-decorated
  methods, grouped by namespace) and the `BrowserSession` that binds one
  WebSocket to the shared `Browser` instance.

This keeps the RPC/transport concerns, the browser-control abstraction, and
the concrete CDP adapter independently testable and swappable.

**Bidirectional streaming over one socket.** A single WebSocket carries two
independent, concurrently running directions:

- *Client → server*: JSON-RPC 2.0 requests (`browser.nav.*`,
  `browser.input.*`, `browser.tabs.*`, `browser.clipboard.*`), served one at
  a time by a `pyrpckit.RpcServer` in `_serve_requests`.
- *Server → client*: JSON-RPC notifications pushed continuously by two
  background tasks — one draining `browser.events()` (tab list, navigation
  state, cursor style, crashes, detachment) and one draining
  `browser.screencast_frames()` — both funneled through a shared send lock
  so frames and events interleave safely on the wire (`browser.event` for
  state, a dedicated frame notification for pixels).

Closing the WebSocket cancels both streaming tasks and tears the session
down; the underlying `Browser` and its Chromium process are owned by the DI
container's lifespan, not by an individual session, so one tab can outlive
a reconnecting client.

**Auth is a gate you provide, not one built in.** The protocol itself has no
authentication or authorization — anyone who can reach the WebSocket can
drive the mirrored tab. BrowserTunnel is meant to sit behind an
authenticating reverse proxy (or be bound to `127.0.0.1` only) that acts as
the access gate; it does not ship its own guard rail.

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

Alternatively, after `npm install` the frontend can be started directly with
`npm run dev`. Before every start, `predev` regenerates the current schemas
from the backend and derives the TypeScript RPC client from them. The Vite
dev server hot-reloads on changes to HTML, CSS, or TypeScript.

Vite proxies all calls under `/api` in development to the backend running
separately on port 8000. The RPC client generated from the OpenRPC schema is
its own npm workspace package, `packages/browser-rpc-client`. The generator
currently lives under `scripts/`; `npm run check:generated` detects stale
generated files.

## Backend protocol

The POC exposes exactly one domain WebSocket router. All client commands run
as JSON-RPC 2.0 over:

- WebSocket: `ws://127.0.0.1:8000/api/browser/ws`
- Full JSON Schema: `/api/browser/schema.json`
- OpenRPC for client generation: `/api/browser/openrpc.json`

Example:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "browser.nav.navigate",
  "params": { "url": "https://example.com" }
}
```

The server sends browser events as the JSON-RPC notification `browser.event`.
`params.type` distinguishes frames, tab and navigation state, and crashed or
detached targets. Frames are JPEG bytes at the application layer and are
base64-encoded only for JSON transport. The `pyrpckit`-decorated methods
cover URL navigation, back, forward, reload, stop-loading, generic
mouse-down/-move/-up input, scrolling, keyboard, text insertion, clipboard,
and tab listing, creation, activation, and closing.

The browser can be configured with `BROWSER_EXECUTABLE`, `BROWSER_CDP_URL`,
`BROWSER_HEADLESS`, `BROWSER_WIDTH`, `BROWSER_HEIGHT`,
`BROWSER_SCREENCAST_QUALITY`, and `BROWSER_STARTUP_TIMEOUT`. Without
`BROWSER_CDP_URL`, the backend launches Chrome, Chromium, or Edge itself.

A real-adapter smoke test is available via
`uv run python -m scripts.smoke_backend`. The protocol has no authentication
yet, so only run the tunnel locally or behind an authenticating reverse
proxy.

# BrowserTunnel

Mirrors a real Chromium tab into a web page. The backend drives the tab over
the Chrome DevTools Protocol, streams its frames to a `<canvas>`, and replays
the viewer's input back onto it. No video codec, just JSON-RPC over a
WebSocket.

Learning project, not a hardened product: no auth, no rate limiting. It's a
reference for the core idea, not something to deploy as is.

### See it in action

<video src="https://github.com/user-attachments/assets/b5fd9da7-6170-4d91-a70f-c37da632d414" controls></video>

*Sped up 1.5x.*

As seen in the video: full clipboard support (copy/read/write round-tripped
through CDP), full tab support (list/create/activate/close, all in sync with
the mirrored session), and cursor shape. The cursor CDP reports has to be
translated into a CSS cursor and played back in the frontend itself, it's
not part of the video stream.

## Architecture

```
┌──────────────────────┐   single WebSocket, JSON-RPC 2.0    ┌───────────────────────────┐
│       Frontend        │ ──────────────────────────────────▶ │          Backend           │
│  (Lit, Lit Canon, Vite)   │  requests: navigate, mouse, key...  │  BrowserSession             │
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

- The tab's screencast comes in frame by frame and gets drawn straight onto
  the canvas. No iframe, no embedded browser engine.
- The tab only exists on the server. Every DOM event the viewer triggers on
  the canvas is translated into a CDP input command and replayed on the real
  tab, so it looks like a real user interacting with it.
- `browsertunnel/src/browsertunnel/features/browser/domain` defines what a browser can do,
  `browsertunnel/src/browsertunnel/features/browser/infrastructure/cdp_browser` implements that over CDP,
  `browsertunnel/src/browsertunnel/features/browser/presentation` exposes it as JSON-RPC.
  Each layer can be swapped without touching the others.
- One socket, both directions running at once: requests go one way, a
  notification stream (frames, tab/nav/cursor state) goes the other.

## Tunneled events

**Navigation:** navigate to URL, back, forward, reload (with optional cache
bypass), stop loading.

**Mouse:** down, move, up, with button, modifier, and click-count tracking
(covers drags and held buttons), plus scroll.

**Keyboard:** key down/up, raw key down, char events, text insertion, and
paste.

**Clipboard:** copy, read, write.

**Tabs:** list, create, activate, close. Every tab command replies with the
full tab list.

**Pushed to the client:** screencast frames, tab list changes, navigation
state (title, URL, loading, can-go-back/forward, error), cursor style, and
target crashed/detached.

## Setup

```bash
uv sync --locked
npm ci --ignore-scripts
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
uv run --locked pytest        # tests
uv run --locked ruff check .  # lint
uv run --locked ruff format . # format
npm run build        # type-check and build the frontend
```

The frontend can also just be started with `npm run dev` after `npm ci --ignore-scripts`.
`predev` regenerates schemas and the RPC client first. Vite hot-reloads on
HTML/CSS/TS changes and proxies `/api` to the backend on port 8000. The
generated client lives in the workspace package `packages/browser-rpc-client`;
`npm run check:generated` flags a stale one.

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
JPEG, base64-encoded for the JSON transport.

Configure the browser via `BROWSER_EXECUTABLE`, `BROWSER_CDP_URL`,
`BROWSER_HEADLESS`, `BROWSER_WIDTH`, `BROWSER_HEIGHT`,
`BROWSER_SCREENCAST_QUALITY`, `BROWSER_STARTUP_TIMEOUT`. Without
`BROWSER_CDP_URL` the backend launches Chrome/Chromium/Edge itself.

Smoke test against a real browser: `uv run --locked python -m scripts.smoke_backend`.


## Canon integration and dependency pins

The backend composition root installs one explicit `browser-tunnel` feature.
Its domain owns the browser ABCs; CDP adapters implement them. Canon owns the
shared Dishka container and closes it after the feature lifespan. RPC methods
are free functions on `RpcChannel`, with `Inject[Browser]`; `RpcService` and the
Dishka router own connection scopes, dispatch and event delivery. The existing
`browser.*` wire names and `/api/browser/ws` endpoint are retained.

The frontend follows Lit Canon's `createApp` → `defineFeature` → `definePage`
composition. A context provider owns the browser session service, and the lazy
Lit page renders tabs, navigation, status and logs from reactive state. The
page releases its socket, DOM listeners and pending frame/log callbacks when
disconnected. Canvas drawing and input translation stay in browser adapters.
This app has a WebSocket RPC API; an OpenAPI HTTP query generator is not needed.

`rpcgen.toml` is the source of truth for the official RPCKit TypeScript generator.
Never edit `packages/browser-rpc-client/src/generated` by hand. Regenerate with
`npm run generate:rpc` after changing the Python contract.

Direct Python/npm dependencies are exact pins; commit `uv.lock` and
`package-lock.json` together with dependency changes. The tested stack uses
`fastapi-canon==0.8.1`, `fastapi-rpckit==0.4.1`, Lit `3.3.3`, and the Lit Canon
Composition `0.1.0` source snapshot described in [vendor/README.md](vendor/README.md).
The snapshot is self-contained and does not require a neighboring checkout.

```bash
uv sync --locked
npm ci --ignore-scripts
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
npm run check:generated
npm run build
uv run --locked python -m scripts.smoke_app
npm run test:browser
```

The app smoke starts a temporary local server and Chromium, exercises both schema
endpoints, tabs, navigation, input, clipboard, pushed events and parse errors,
then closes both. The UI smoke checks the same connection through Lit and tests
page disposal/reconnection. On Windows it uses installed Chrome; on Linux/macOS
install Playwright Chromium first with `npx playwright install chromium` and set
`BROWSER_EXECUTABLE` to its executable path if no system Chrome is available.
CI runs the pinned installs, generated-client check, tests, build and both smokes.

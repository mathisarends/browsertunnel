import "./style.css";
import {
  BrowserTunnelClient,
  WebSocketRpcTransport,
  type BrowserEvent,
  type ClickParams,
  type CursorStyle as BrowserCursor,
  type HoverParams,
  type RpcTransport,
  type TabResult as BrowserTab,
} from "@browsertunnel/browser-rpc-client";

type EventPayload = Record<string, unknown>;
type HoverPoint = Pick<HoverParams, "x" | "y">;

const HOVER_LOG_IDLE_MS = 250;
const HOVER_METHOD = "browser.input.hover";
const MAX_LOG_ENTRIES = 200;
const KEPT_LOG_ENTRIES = 150;

function element<T extends Element>(selector: string): T {
  const found = document.querySelector<T>(selector);
  if (!found) throw new Error(`Required element not found: ${selector}`);
  return found;
}

const canvas = element<HTMLCanvasElement>("#browser-canvas");
const addressForm = element<HTMLFormElement>("#address-form");
const addressInput = element<HTMLInputElement>("#address-input");
const tabList = element<HTMLDivElement>("#tab-list");
const newTabButton = element<HTMLButtonElement>("#new-tab");
const activeTabStatus = element<HTMLSpanElement>("#active-tab-status");
const cursorStatus = element<HTMLSpanElement>("#cursor-status");
const eventLog = element<HTMLOListElement>("#event-log");
const emptyLog = element<HTMLParagraphElement>("#empty-log");
const clearLogsButton = element<HTMLButtonElement>("#clear-logs");

let tabs: BrowserTab[] = [];
let latestFrame: string | undefined;
let renderingFrame = false;
let latestHover: HoverParams | undefined;
let hoverFrame: number | undefined;
let hoverInFlight = false;
let hoverLogTimer: ReturnType<typeof setTimeout> | undefined;
let hoverLogStart: HoverPoint | undefined;
let hoverLogEnd: HoverPoint | undefined;
let hoverLogMoves = 0;
let lastHoverPoint: HoverPoint | undefined;
let lastLoggedCursor: BrowserCursor | undefined;

// Erst ab MAX_LOG_ENTRIES kappen, dafür gleich auf KEPT_LOG_ENTRIES herunter,
// damit nicht bei jedem Event ein einzelner Knoten aus dem DOM fällt.
function pruneLog(): void {
  if (eventLog.childElementCount <= MAX_LOG_ENTRIES) return;
  const stale = Array.from(eventLog.children).slice(0, eventLog.childElementCount - KEPT_LOG_ENTRIES);
  for (const entry of stale) entry.remove();
}

function log(direction: "incoming" | "outgoing", name: string, payload: EventPayload = {}): void {
  const entry = document.createElement("li");
  entry.className = `log-entry ${direction}`;
  const meta = document.createElement("div");
  meta.className = "log-meta";
  const directionLabel = document.createElement("span");
  directionLabel.textContent = direction === "outgoing" ? "OUT" : "IN";
  const eventName = document.createElement("strong");
  eventName.textContent = name;
  const timestamp = document.createElement("time");
  timestamp.textContent = new Date().toLocaleTimeString("de-DE", { hour12: false });
  const data = document.createElement("pre");
  data.textContent = JSON.stringify(payload, null, 2);
  meta.append(directionLabel, eventName, timestamp);
  entry.append(meta, data);
  eventLog.append(entry);
  pruneLog();
  emptyLog.hidden = true;
  eventLog.scrollTop = eventLog.scrollHeight;
}

function reportError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  activeTabStatus.textContent = `Fehler · ${message}`;
  log("incoming", "client.error", { message });
}

function normalizeUrl(value: string): string {
  return /^[a-z][a-z\d+.-]*:/i.test(value) ? value : `https://${value}`;
}

function activeTab(): BrowserTab | undefined {
  return tabs.find((tab) => tab.active);
}

function applyTabs(nextTabs: BrowserTab[]): void {
  tabs = nextTabs;
  const active = activeTab();
  if (active) {
    addressInput.value = active.url === "about:blank" ? "" : active.url;
    activeTabStatus.textContent = `${active.title || "Neuer Tab"} · verbunden`;
  }
  renderTabs();
}

function renderTabs(): void {
  tabList.replaceChildren(
    ...tabs.map((tab) => {
      const tabElement = document.createElement("div");
      tabElement.className = "browser-tab";
      tabElement.role = "tab";
      tabElement.tabIndex = tab.active ? 0 : -1;
      tabElement.ariaSelected = String(tab.active);

      const favicon = document.createElement("i");
      favicon.ariaHidden = "true";
      const title = document.createElement("span");
      title.textContent = tab.title || "Neuer Tab";
      const close = document.createElement("button");
      close.type = "button";
      close.className = "close-tab";
      close.ariaLabel = `${title.textContent} schließen`;
      close.textContent = "×";
      close.addEventListener("click", (event) => {
        event.stopPropagation();
        void client.browser.tab.close({ tabId: tab.id }).then((result) =>
          applyTabs(result.tabs),
        ).catch(reportError);
      });
      tabElement.addEventListener("click", () => {
        void client.browser.tab.activate({ tabId: tab.id }).then((result) =>
          applyTabs(result.tabs),
        ).catch(reportError);
      });
      tabElement.append(favicon, title, close);
      return tabElement;
    }),
  );
}

async function renderLatestFrame(): Promise<void> {
  if (renderingFrame) return;
  renderingFrame = true;
  try {
    while (latestFrame) {
      const encoded = latestFrame;
      latestFrame = undefined;
      const binary = atob(encoded);
      const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
      const bitmap = await createImageBitmap(new Blob([bytes], { type: "image/jpeg" }));
      if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
      }
      canvas.getContext("2d")?.drawImage(bitmap, 0, 0);
      bitmap.close();
    }
  } finally {
    renderingFrame = false;
  }
}

function applyCursor(cursor: BrowserCursor): void {
  canvas.style.cursor = cursor;
  cursorStatus.textContent = `cursor: ${cursor}`;
}

function receive(event: BrowserEvent): void {
  if (event.type === "browser.frame") {
    latestFrame = event.data;
    void renderLatestFrame().catch(reportError);
    return;
  }

  if (event.type === "browser.cursor") {
    applyCursor(event.cursor);
    if (event.cursor !== lastLoggedCursor) {
      lastLoggedCursor = event.cursor;
      log("incoming", event.type, { cursor: event.cursor });
    }
    return;
  }

  log("incoming", event.type, event as unknown as EventPayload);
  if (event.type === "browser.tabs") {
    applyTabs(event.tabs);
  } else if (event.type === "browser.navigation") {
    tabs = tabs.map((tab) =>
      tab.id === event.tabId ? { ...tab, title: event.title, url: event.url } : tab,
    );
    if (activeTab()?.id === event.tabId) {
      addressInput.value = event.url;
      activeTabStatus.textContent = `${event.title || "Neuer Tab"} · ${event.loading ? "lädt" : "verbunden"}`;
    }
    renderTabs();
  } else if (event.type === "browser.targetCrashed") {
    activeTabStatus.textContent = `Browser abgestürzt · ${event.status}`;
  }
}

class LoggingRpcTransport implements RpcTransport {
  constructor(private readonly transport: RpcTransport) {}

  request<TResult>(method: string, params?: object): Promise<TResult> {
    // Hover feuert pro Frame; geloggt wird stattdessen die gesettelte Bewegung.
    if (method !== HOVER_METHOD) log("outgoing", method, (params ?? {}) as EventPayload);
    return this.transport.request<TResult>(method, params);
  }

  notifications(): AsyncIterable<unknown> {
    return this.transport.notifications();
  }

  close(): Promise<void> {
    return this.transport.close();
  }
}

const socketUrl = new URL("/api/browser/ws", window.location.href);
socketUrl.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const socketTransport = new WebSocketRpcTransport(socketUrl);
const client = new BrowserTunnelClient(new LoggingRpcTransport(socketTransport));

async function receiveNotifications(): Promise<void> {
  for await (const notification of client.notifications()) receive(notification.params);
}

function canvasPoint(event: MouseEvent | WheelEvent): { x: number; y: number } {
  const bounds = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - bounds.left) / bounds.width) * canvas.width,
    y: ((event.clientY - bounds.top) / bounds.height) * canvas.height,
  };
}

function mouseModifiers(event: MouseEvent): number {
  return (
    Number(event.altKey) +
    Number(event.ctrlKey) * 2 +
    Number(event.metaKey) * 4 +
    Number(event.shiftKey) * 8
  );
}

function sendClick(params: ClickParams): void {
  void client.browser.input.click(params).catch(reportError);
}

function documentHover(params: HoverParams): void {
  const point = { x: params.x, y: params.y };
  hoverLogStart ??= lastHoverPoint ?? point;
  hoverLogEnd = point;
  hoverLogMoves += 1;
  lastHoverPoint = point;

  if (hoverLogTimer !== undefined) clearTimeout(hoverLogTimer);
  hoverLogTimer = setTimeout(() => {
    hoverLogTimer = undefined;
    if (!hoverLogStart || !hoverLogEnd) return;

    log("outgoing", HOVER_METHOD, {
      from: hoverLogStart,
      to: hoverLogEnd,
      moves: hoverLogMoves,
    });
    hoverLogStart = undefined;
    hoverLogEnd = undefined;
    hoverLogMoves = 0;
  }, HOVER_LOG_IDLE_MS);
}

function scheduleHover(params: HoverParams): void {
  documentHover(params);
  latestHover = params;
  queueHover();
}

function queueHover(): void {
  if (hoverFrame !== undefined || hoverInFlight) return;

  hoverFrame = requestAnimationFrame(() => {
    hoverFrame = undefined;
    const next = latestHover;
    latestHover = undefined;
    if (!next) return;

    hoverInFlight = true;
    void client.browser.input.hover(next).catch(reportError).finally(() => {
      hoverInFlight = false;
      if (latestHover) queueHover();
    });
  });
}

addressForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = addressInput.value.trim();
  if (value) void client.browser.nav.navigate({ url: normalizeUrl(value) }).catch(reportError);
});

newTabButton.addEventListener("click", () => {
  void client.browser.tab.create({ url: "about:blank" }).then((result) => {
    applyTabs(result.tabs);
    addressInput.focus();
  }).catch(reportError);
});

canvas.tabIndex = 0;
canvas.addEventListener("mousedown", (event) => {
  canvas.focus();
  sendClick({
    type: "mousePressed",
    ...canvasPoint(event),
    button: "left",
    buttons: 1,
    clickCount: event.detail,
  });
});
canvas.addEventListener("mouseup", (event) => {
  sendClick({
    type: "mouseReleased",
    ...canvasPoint(event),
    button: "left",
    buttons: 0,
    clickCount: event.detail,
  });
});
canvas.addEventListener("mousemove", (event) => {
  scheduleHover({
    ...canvasPoint(event),
    buttons: event.buttons,
    modifiers: mouseModifiers(event),
  });
});
canvas.addEventListener("mouseleave", (event) => {
  scheduleHover({
    ...canvasPoint(event),
    buttons: event.buttons,
    modifiers: mouseModifiers(event),
  });
});
canvas.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    void client.browser.input.scroll({
      ...canvasPoint(event),
      deltaX: event.deltaX,
      deltaY: event.deltaY,
    }).catch(reportError);
  },
  { passive: false },
);
function isPasteShortcut(event: KeyboardEvent): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "v";
}

function isCopyShortcut(event: KeyboardEvent): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey && event.key.toLowerCase() === "c";
}

// Forwarding the key events alone never copies: Chrome only runs the copy
// command when it is dispatched explicitly, and the copied text then lives in
// the container's clipboard until we mirror it onto the viewer's.
async function copyFromPage(): Promise<void> {
  const { text } = await client.browser.clipboard.copy();
  if (!text) return;
  await navigator.clipboard.writeText(text);
  log("incoming", "browser.clipboard.copy", { characters: text.length });
}

document.addEventListener("paste", (event) => {
  if (document.activeElement !== canvas) return;
  event.preventDefault();
  const text = event.clipboardData?.getData("text/plain");
  if (!text) return;

  void client.browser.input.paste({ text }).catch(reportError);
});

canvas.addEventListener("keydown", (event) => {
  // Let the browser turn the shortcut into a paste event carrying the clipboard.
  if (isPasteShortcut(event)) return;
  if (isCopyShortcut(event)) {
    event.preventDefault();
    void copyFromPage().catch(reportError);
    return;
  }
  event.preventDefault();
  const modifiers = Number(event.altKey) + Number(event.ctrlKey) * 2 + Number(event.metaKey) * 4 + Number(event.shiftKey) * 8;
  if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
    void client.browser.input.text.insert({ text: event.key }).catch(reportError);
  } else {
    void client.browser.input.key({
      type: "keyDown",
      key: event.key,
      code: event.code,
      modifiers,
    }).catch(reportError);
  }
});
canvas.addEventListener("keyup", (event) => {
  if (isPasteShortcut(event) || isCopyShortcut(event)) return;
  if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) return;
  const modifiers = Number(event.altKey) + Number(event.ctrlKey) * 2 + Number(event.metaKey) * 4 + Number(event.shiftKey) * 8;
  void client.browser.input.key({
    type: "keyUp",
    key: event.key,
    code: event.code,
    modifiers,
  }).catch(reportError);
});

clearLogsButton.addEventListener("click", () => {
  eventLog.replaceChildren();
  emptyLog.hidden = false;
});

socketTransport
  .connect()
  .then(async () => {
    activeTabStatus.textContent = "Backend verbunden · Stream wartet";
    void receiveNotifications().catch(reportError);
    const result = await client.browser.tab.list();
    applyTabs(result.tabs);
  })
  .catch(reportError);

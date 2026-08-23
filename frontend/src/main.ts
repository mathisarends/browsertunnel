import "./style.css";
import {
  BrowserTunnelClient,
  WebSocketRpcTransport,
  type BrowserEvent,
  type CursorStyle as BrowserCursor,
  type MouseParams,
  type RpcTransport,
  type TabResult as BrowserTab,
} from "@browsertunnel/browser-rpc-client";

type EventPayload = Record<string, unknown>;
type MousePoint = Pick<MouseParams, "x" | "y">;

const MOUSE_LOG_IDLE_MS = 250;
const MOUSE_METHOD = "browser.input.mouse";
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
let latestMouseMove: MouseParams | undefined;
let mouseMoveFrame: number | undefined;
let mouseInputTail: Promise<void> = Promise.resolve();
let mouseLogTimer: ReturnType<typeof setTimeout> | undefined;
let mouseLogStart: MousePoint | undefined;
let mouseLogEnd: MousePoint | undefined;
let mouseLogMoves = 0;
let lastMousePoint: MousePoint | undefined;
let lastLoggedCursor: BrowserCursor | undefined;

// Erst ab MAX_LOG_ENTRIES kappen, dafür gleich auf KEPT_LOG_ENTRIES herunter,
// damit nicht bei jedem Event ein einzelner Knoten aus dem DOM fällt.
function pruneLog(): void {
  if (eventLog.childElementCount <= MAX_LOG_ENTRIES) return;
  const stale = Array.from(eventLog.children).slice(
    0,
    eventLog.childElementCount - KEPT_LOG_ENTRIES,
  );
  for (const entry of stale) entry.remove();
}

function log(
  direction: "incoming" | "outgoing",
  name: string,
  payload: EventPayload = {},
): void {
  const entry = document.createElement("li");
  entry.className = `log-entry ${direction}`;
  const meta = document.createElement("div");
  meta.className = "log-meta";
  const directionLabel = document.createElement("span");
  directionLabel.textContent = direction === "outgoing" ? "OUT" : "IN";
  const eventName = document.createElement("strong");
  eventName.textContent = name;
  const timestamp = document.createElement("time");
  timestamp.textContent = new Date().toLocaleTimeString("de-DE", {
    hour12: false,
  });
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
        void client.browser.tab
          .close({ tabId: tab.id })
          .then((result) => applyTabs(result.tabs))
          .catch(reportError);
      });
      tabElement.addEventListener("click", () => {
        void client.browser.tab
          .activate({ tabId: tab.id })
          .then((result) => applyTabs(result.tabs))
          .catch(reportError);
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
      const bytes = Uint8Array.from(binary, (character) =>
        character.charCodeAt(0),
      );
      const bitmap = await createImageBitmap(
        new Blob([bytes], { type: "image/jpeg" }),
      );
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
      tab.id === event.tabId
        ? { ...tab, title: event.title, url: event.url }
        : tab,
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
    // Mouse-Moves feuern pro Frame; geloggt wird stattdessen die gesettelte Bewegung.
    if (method !== MOUSE_METHOD)
      log("outgoing", method, (params ?? {}) as EventPayload);
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
const client = new BrowserTunnelClient(
  new LoggingRpcTransport(socketTransport),
);

async function receiveNotifications(): Promise<void> {
  for await (const notification of client.notifications())
    receive(notification.params);
}

function canvasPoint(event: MouseEvent | WheelEvent): { x: number; y: number } {
  const bounds = canvas.getBoundingClientRect();
  return {
    x: ((event.clientX - bounds.left) / bounds.width) * canvas.width,
    y: ((event.clientY - bounds.top) / bounds.height) * canvas.height,
  };
}

function inputModifiers(event: MouseEvent | KeyboardEvent): number {
  return (
    Number(event.altKey) +
    Number(event.ctrlKey) * 2 +
    Number(event.metaKey) * 4 +
    Number(event.shiftKey) * 8
  );
}

function enqueueMouse(params: MouseParams): void {
  mouseInputTail = mouseInputTail
    .then(() => client.browser.input.mouse(params))
    .catch(reportError);
}

function documentMouseMove(params: MouseParams): void {
  const point = { x: params.x, y: params.y };
  mouseLogStart ??= lastMousePoint ?? point;
  mouseLogEnd = point;
  mouseLogMoves += 1;
  lastMousePoint = point;

  if (mouseLogTimer !== undefined) clearTimeout(mouseLogTimer);
  mouseLogTimer = setTimeout(() => {
    mouseLogTimer = undefined;
    if (!mouseLogStart || !mouseLogEnd) return;

    log("outgoing", MOUSE_METHOD, {
      from: mouseLogStart,
      to: mouseLogEnd,
      moves: mouseLogMoves,
    });
    mouseLogStart = undefined;
    mouseLogEnd = undefined;
    mouseLogMoves = 0;
  }, MOUSE_LOG_IDLE_MS);
}

function scheduleMouseMove(params: MouseParams): void {
  documentMouseMove(params);
  latestMouseMove = params;
  if (mouseMoveFrame !== undefined) return;
  mouseMoveFrame = requestAnimationFrame(flushMouseMove);
}

function flushMouseMove(): void {
  if (mouseMoveFrame !== undefined) cancelAnimationFrame(mouseMoveFrame);
  mouseMoveFrame = undefined;
  const next = latestMouseMove;
  latestMouseMove = undefined;
  if (next) enqueueMouse(next);
}

addressForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = addressInput.value.trim();
  if (value)
    void client.browser.nav
      .navigate({ url: normalizeUrl(value) })
      .catch(reportError);
});

newTabButton.addEventListener("click", () => {
  void client.browser.tab
    .create({ url: "about:blank" })
    .then((result) => {
      applyTabs(result.tabs);
      addressInput.focus();
    })
    .catch(reportError);
});

canvas.tabIndex = 0;
const MOUSE_BUTTONS = ["left", "middle", "right", "back", "forward"] as const;
const pressedMouseButtons = new Map<number, MouseParams["button"]>();

function mouseButton(button: number): MouseParams["button"] {
  return MOUSE_BUTTONS[button] ?? "none";
}

canvas.addEventListener("mousedown", (event) => {
  event.preventDefault();
  canvas.focus();
  pressedMouseButtons.set(event.button, mouseButton(event.button));
  flushMouseMove();
  enqueueMouse({
    type: "mouseDown",
    ...canvasPoint(event),
    button: mouseButton(event.button),
    buttons: event.buttons,
    modifiers: inputModifiers(event),
    clickCount: event.detail,
  });
});

window.addEventListener("mouseup", (event) => {
  const button = pressedMouseButtons.get(event.button);
  if (button === undefined) return;
  event.preventDefault();
  flushMouseMove();
  enqueueMouse({
    type: "mouseUp",
    ...canvasPoint(event),
    button,
    buttons: event.buttons,
    modifiers: inputModifiers(event),
    clickCount: event.detail,
  });
  pressedMouseButtons.delete(event.button);
});

function forwardMouseMove(event: MouseEvent): void {
  scheduleMouseMove({
    type: "mouseMove",
    ...canvasPoint(event),
    button: "none",
    buttons: event.buttons,
    modifiers: inputModifiers(event),
    clickCount: 0,
  });
}

canvas.addEventListener("mousemove", (event) => {
  if (pressedMouseButtons.size === 0) forwardMouseMove(event);
});
canvas.addEventListener("mouseleave", (event) => {
  if (pressedMouseButtons.size === 0) forwardMouseMove(event);
});
window.addEventListener("mousemove", (event) => {
  if (pressedMouseButtons.size > 0) forwardMouseMove(event);
});
window.addEventListener("blur", () => {
  if (pressedMouseButtons.size === 0) return;
  flushMouseMove();
  const point = lastMousePoint ?? { x: 0, y: 0 };
  for (const button of pressedMouseButtons.values()) {
    enqueueMouse({
      type: "mouseUp",
      ...point,
      button,
      buttons: 0,
      clickCount: 0,
    });
  }
  pressedMouseButtons.clear();
});
canvas.addEventListener("contextmenu", (event) => event.preventDefault());
canvas.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    void client.browser.input
      .scroll({
        ...canvasPoint(event),
        deltaX: event.deltaX,
        deltaY: event.deltaY,
      })
      .catch(reportError);
  },
  { passive: false },
);
function isPasteShortcut(event: KeyboardEvent): boolean {
  return (
    (event.ctrlKey || event.metaKey) &&
    !event.altKey &&
    event.key.toLowerCase() === "v"
  );
}

function isCopyShortcut(event: KeyboardEvent): boolean {
  return (
    (event.ctrlKey || event.metaKey) &&
    !event.altKey &&
    event.key.toLowerCase() === "c"
  );
}

const WINDOWS_VIRTUAL_KEY_BY_CODE: Readonly<Record<string, number>> = {
  Backspace: 8,
  Tab: 9,
  Enter: 13,
  NumpadEnter: 13,
  ShiftLeft: 16,
  ShiftRight: 16,
  ControlLeft: 17,
  ControlRight: 17,
  AltLeft: 18,
  AltRight: 18,
  Pause: 19,
  CapsLock: 20,
  Escape: 27,
  Space: 32,
  PageUp: 33,
  PageDown: 34,
  End: 35,
  Home: 36,
  ArrowLeft: 37,
  ArrowUp: 38,
  ArrowRight: 39,
  ArrowDown: 40,
  Insert: 45,
  Delete: 46,
  MetaLeft: 91,
  MetaRight: 92,
  ContextMenu: 93,
  NumpadMultiply: 106,
  NumpadAdd: 107,
  NumpadSubtract: 109,
  NumpadDecimal: 110,
  NumpadDivide: 111,
  NumLock: 144,
  ScrollLock: 145,
  Semicolon: 186,
  Equal: 187,
  Comma: 188,
  Minus: 189,
  Period: 190,
  Slash: 191,
  Backquote: 192,
  BracketLeft: 219,
  Backslash: 220,
  BracketRight: 221,
  Quote: 222,
};

function windowsVirtualKeyCode(event: KeyboardEvent): number {
  const mapped = WINDOWS_VIRTUAL_KEY_BY_CODE[event.code];
  if (mapped !== undefined) return mapped;
  if (/^Key[A-Z]$/.test(event.code)) return event.code.charCodeAt(3);
  if (/^Digit[0-9]$/.test(event.code)) return event.code.charCodeAt(5);
  if (/^Numpad[0-9]$/.test(event.code)) return 96 + Number(event.code.at(-1));
  if (/^F(?:[1-9]|1[0-9]|2[0-4])$/.test(event.code)) {
    return 111 + Number(event.code.slice(1));
  }
  return event.keyCode;
}

function keyText(event: KeyboardEvent): string | undefined {
  const hasAccelerator = event.altKey || event.ctrlKey || event.metaKey;
  if (event.key === "Enter" && !hasAccelerator) return "\r";
  const isAltGraph = event.getModifierState("AltGraph");
  if (event.key.length === 1 && (!hasAccelerator || isAltGraph))
    return event.key;
  return undefined;
}

function sendKey(
  event: KeyboardEvent,
  type: "rawKeyDown" | "keyDown" | "keyUp",
): void {
  const virtualKeyCode = windowsVirtualKeyCode(event);
  const text = type === "keyDown" ? keyText(event) : undefined;
  void client.browser.input
    .key({
      type,
      key: event.key,
      code: event.code,
      text,
      unmodifiedText: text,
      modifiers: inputModifiers(event),
      autoRepeat: event.repeat,
      windowsVirtualKeyCode: virtualKeyCode,
      nativeVirtualKeyCode: virtualKeyCode,
      location: event.location,
      isKeypad: event.location === KeyboardEvent.DOM_KEY_LOCATION_NUMPAD,
      isSystemKey: event.altKey,
    })
    .catch(reportError);
}

// The key chord performs the remote copy. This RPC additionally reads the remote
// clipboard so the result can cross the process boundary into the viewer clipboard.
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
  sendKey(event, keyText(event) === undefined ? "rawKeyDown" : "keyDown");
});
canvas.addEventListener("keyup", (event) => {
  if (isPasteShortcut(event) || isCopyShortcut(event)) return;
  event.preventDefault();
  sendKey(event, "keyUp");
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

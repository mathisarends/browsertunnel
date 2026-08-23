import "./style.css";
import {
  BrowserClient,
  type BrowserEvent,
  type BrowserTab,
  type MouseMoveParams,
} from "./api";

type EventPayload = Record<string, unknown>;

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
const eventLog = element<HTMLOListElement>("#event-log");
const emptyLog = element<HTMLParagraphElement>("#empty-log");
const clearLogsButton = element<HTMLButtonElement>("#clear-logs");

let tabs: BrowserTab[] = [];
let latestFrame: string | undefined;
let renderingFrame = false;
let latestMouseMove: MouseMoveParams | undefined;
let mouseMoveFrame: number | undefined;
let mouseMoveInFlight = false;

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
        void rpc<{ tabs: BrowserTab[] }>("browser.tab.close", { tabId: tab.id }).then((result) =>
          applyTabs(result.tabs),
        ).catch(reportError);
      });
      tabElement.addEventListener("click", () => {
        void rpc<{ tabs: BrowserTab[] }>("browser.tab.activate", { tabId: tab.id }).then((result) =>
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
      canvas.getContext("2d")?.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
      bitmap.close();
    }
  } finally {
    renderingFrame = false;
  }
}

function receive(event: BrowserEvent): void {
  if (event.type === "browser.frame") {
    latestFrame = event.data;
    void renderLatestFrame().catch(reportError);
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

const client = new BrowserClient(receive);

function rpc<T = Record<string, never>>(method: string, params: object = {}): Promise<T> {
  log("outgoing", method, params as EventPayload);
  return client.call<T>(method, params);
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

function scheduleMouseMove(params: MouseMoveParams): void {
  latestMouseMove = params;
  if (mouseMoveFrame !== undefined || mouseMoveInFlight) return;

  mouseMoveFrame = requestAnimationFrame(() => {
    mouseMoveFrame = undefined;
    const next = latestMouseMove;
    latestMouseMove = undefined;
    if (!next) return;

    mouseMoveInFlight = true;
    log("outgoing", "browser.mouse", { type: "mouseMoved", ...next });
    void client.mouseMove(next).catch(reportError).finally(() => {
      mouseMoveInFlight = false;
      if (latestMouseMove) scheduleMouseMove(latestMouseMove);
    });
  });
}

addressForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = addressInput.value.trim();
  if (value) void rpc("browser.navigate", { url: normalizeUrl(value) }).catch(reportError);
});

newTabButton.addEventListener("click", () => {
  void rpc<{ tabs: BrowserTab[] }>("browser.tab.create", { url: "about:blank" }).then((result) => {
    applyTabs(result.tabs);
    addressInput.focus();
  }).catch(reportError);
});

canvas.tabIndex = 0;
canvas.addEventListener("mousedown", (event) => {
  canvas.focus();
  void rpc("browser.mouse", {
    type: "mousePressed",
    ...canvasPoint(event),
    button: "left",
    buttons: 1,
    clickCount: event.detail,
  }).catch(reportError);
});
canvas.addEventListener("mouseup", (event) => {
  void rpc("browser.mouse", {
    type: "mouseReleased",
    ...canvasPoint(event),
    button: "left",
    buttons: 0,
    clickCount: event.detail,
  }).catch(reportError);
});
canvas.addEventListener("mousemove", (event) => {
  scheduleMouseMove({
    ...canvasPoint(event),
    buttons: event.buttons,
    modifiers: mouseModifiers(event),
  });
});
canvas.addEventListener("mouseleave", (event) => {
  scheduleMouseMove({
    ...canvasPoint(event),
    buttons: event.buttons,
    modifiers: mouseModifiers(event),
  });
});
canvas.addEventListener(
  "wheel",
  (event) => {
    event.preventDefault();
    void rpc("browser.scroll", { ...canvasPoint(event), deltaX: event.deltaX, deltaY: event.deltaY }).catch(reportError);
  },
  { passive: false },
);
canvas.addEventListener("keydown", (event) => {
  event.preventDefault();
  const modifiers = Number(event.altKey) + Number(event.ctrlKey) * 2 + Number(event.metaKey) * 4 + Number(event.shiftKey) * 8;
  if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) {
    void rpc("browser.text.insert", { text: event.key }).catch(reportError);
  } else {
    void rpc("browser.key", { type: "keyDown", key: event.key, code: event.code, modifiers }).catch(reportError);
  }
});
canvas.addEventListener("keyup", (event) => {
  if (event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey) return;
  const modifiers = Number(event.altKey) + Number(event.ctrlKey) * 2 + Number(event.metaKey) * 4 + Number(event.shiftKey) * 8;
  void rpc("browser.key", { type: "keyUp", key: event.key, code: event.code, modifiers }).catch(reportError);
});

clearLogsButton.addEventListener("click", () => {
  eventLog.replaceChildren();
  emptyLog.hidden = false;
});

client
  .connect()
  .then(async () => {
    activeTabStatus.textContent = "Backend verbunden · Stream wartet";
    const result = await rpc<{ tabs: BrowserTab[] }>("browser.tab.list");
    applyTabs(result.tabs);
  })
  .catch(reportError);

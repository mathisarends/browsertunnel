import "./style.css";

type EventDirection = "incoming" | "outgoing";
type EventPayload = Record<string, unknown>;
type BrowserTab = {
  id: string;
  title: string;
  url: string;
};

function requireElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Required element not found: ${selector}`);
  }

  return element;
}

const canvas = requireElement<HTMLCanvasElement>("#browser-canvas");
const addressForm = requireElement<HTMLFormElement>("#address-form");
const addressInput = requireElement<HTMLInputElement>("#address-input");
const tabList = requireElement<HTMLDivElement>("#tab-list");
const newTabButton = requireElement<HTMLButtonElement>("#new-tab");
const activeTabStatus = requireElement<HTMLSpanElement>("#active-tab-status");
const eventLog = requireElement<HTMLOListElement>("#event-log");
const emptyLog = requireElement<HTMLParagraphElement>("#empty-log");
const clearLogsButton = requireElement<HTMLButtonElement>("#clear-logs");

let nextTabNumber = 2;
let tabs: BrowserTab[] = [
  { id: "tab-1", title: "Example", url: "https://example.com" },
];
let activeTabId = tabs[0].id;

function formatPayload(payload: EventPayload): string {
  return JSON.stringify(payload, null, 2);
}

function appendEvent(direction: EventDirection, name: string, payload: EventPayload): void {
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

  const payloadElement = document.createElement("pre");
  payloadElement.textContent = formatPayload(payload);

  meta.append(directionLabel, eventName, timestamp);
  entry.append(meta, payloadElement);
  eventLog.append(entry);
  emptyLog.hidden = true;
  eventLog.scrollTop = eventLog.scrollHeight;
}

function getActiveTab(): BrowserTab {
  const activeTab = tabs.find((tab) => tab.id === activeTabId);

  if (!activeTab) {
    throw new Error(`Active tab not found: ${activeTabId}`);
  }

  return activeTab;
}

function titleFromUrl(url: string): string {
  if (!url) {
    return "Neuer Tab";
  }

  try {
    return new URL(url).hostname || url;
  } catch {
    return url;
  }
}

function normalizeUrl(value: string): string {
  return /^[a-z][a-z\d+.-]*:/i.test(value) ? value : `https://${value}`;
}

function activateTab(tabId: string, emitEvent = true): void {
  activeTabId = tabId;
  const tab = getActiveTab();
  addressInput.value = tab.url;
  activeTabStatus.textContent = `${tab.title} · Stream wartet`;
  renderTabs();

  if (emitEvent) {
    recordOutgoingEvent("tab.activated", { tabId });
  }
}

function createTab(): void {
  const id = `tab-${nextTabNumber++}`;
  const tab = { id, title: "Neuer Tab", url: "" };
  tabs.push(tab);
  activateTab(id, false);
  recordOutgoingEvent("tab.created", { tabId: id });
  addressInput.focus();
}

function closeTab(tabId: string): void {
  const closedIndex = tabs.findIndex((tab) => tab.id === tabId);

  if (closedIndex < 0) {
    return;
  }

  tabs.splice(closedIndex, 1);
  recordOutgoingEvent("tab.closed", { tabId });

  if (tabs.length === 0) {
    createTab();
    return;
  }

  if (activeTabId === tabId) {
    const fallbackTab = tabs[Math.min(closedIndex, tabs.length - 1)];
    activateTab(fallbackTab.id, false);
  } else {
    renderTabs();
  }
}

function renderTabs(): void {
  const tabElements = tabs.map((tab) => {
    const tabElement = document.createElement("div");
    tabElement.className = "browser-tab";
    tabElement.dataset.tabId = tab.id;
    tabElement.role = "tab";
    tabElement.tabIndex = tab.id === activeTabId ? 0 : -1;
    tabElement.ariaSelected = String(tab.id === activeTabId);

    const favicon = document.createElement("i");
    favicon.setAttribute("aria-hidden", "true");

    const title = document.createElement("span");
    title.textContent = tab.title;

    const closeButton = document.createElement("button");
    closeButton.type = "button";
    closeButton.className = "close-tab";
    closeButton.ariaLabel = `${tab.title} schließen`;
    closeButton.textContent = "×";
    closeButton.addEventListener("click", (event) => {
      event.stopPropagation();
      closeTab(tab.id);
    });

    tabElement.addEventListener("click", () => activateTab(tab.id));
    tabElement.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activateTab(tab.id);
      }
    });

    tabElement.append(favicon, title, closeButton);
    return tabElement;
  });

  tabList.replaceChildren(...tabElements);
}

addressForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const value = addressInput.value.trim();
  if (value) {
    const url = normalizeUrl(value);
    const tab = getActiveTab();
    tab.url = url;
    tab.title = titleFromUrl(url);
    addressInput.value = url;
    renderTabs();
    activeTabStatus.textContent = `${tab.title} · Stream wartet`;
    recordOutgoingEvent("navigate", { tabId: tab.id, url });
  }
});

newTabButton.addEventListener("click", createTab);

clearLogsButton.addEventListener("click", () => {
  eventLog.replaceChildren();
  emptyLog.hidden = false;
});

export function recordOutgoingEvent(name: string, payload: EventPayload = {}): void {
  appendEvent("outgoing", name, payload);
}

export function recordIncomingEvent(name: string, payload: EventPayload = {}): void {
  appendEvent("incoming", name, payload);
}

// A future framecast client can draw decoded frames into this canvas.
export function drawFrame(frame: CanvasImageSource): void {
  const context = canvas.getContext("2d");
  context?.drawImage(frame, 0, 0, canvas.width, canvas.height);
}

renderTabs();

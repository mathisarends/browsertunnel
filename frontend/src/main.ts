import "./style.css";
import {
  BrowserTunnelClient,
  WebSocketRpcTransport,
  type RpcTransport,
} from "@browsertunnel/browser-rpc-client";
import { BrowserInput, MOUSE_METHOD } from "./browser-input";
import {
  BrowserView,
  type BrowserViewElements,
  type EventPayload,
} from "./browser-view";

function requiredElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);
  if (!element) throw new Error(`Required element not found: ${selector}`);
  return element;
}

const elements: BrowserViewElements = {
  canvas: requiredElement("#browser-canvas"),
  addressInput: requiredElement("#address-input"),
  tabList: requiredElement("#tab-list"),
  activeTabStatus: requiredElement("#active-tab-status"),
  cursorStatus: requiredElement("#cursor-status"),
  eventLog: requiredElement("#event-log"),
  emptyLog: requiredElement("#empty-log"),
};
const addressForm = requiredElement<HTMLFormElement>("#address-form");
const newTabButton = requiredElement<HTMLButtonElement>("#new-tab");
const clearLogsButton = requiredElement<HTMLButtonElement>("#clear-logs");

let view: BrowserView;

function reportError(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  elements.activeTabStatus.textContent = `Fehler · ${message}`;
  view.log("incoming", "client.error", { message });
}

class LoggingRpcTransport implements RpcTransport {
  constructor(private readonly transport: RpcTransport) {}

  request<TResult>(method: string, params?: object): Promise<TResult> {
    if (method !== MOUSE_METHOD) {
      view.log("outgoing", method, (params ?? {}) as EventPayload);
    }
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

view = new BrowserView(elements, {
  activateTab: async (tabId) =>
    (await client.browser.tab.activate({ tabId })).tabs,
  closeTab: async (tabId) => (await client.browser.tab.close({ tabId })).tabs,
  reportError,
});

new BrowserInput(
  elements.canvas,
  client,
  reportError,
  (payload) => view.log("outgoing", MOUSE_METHOD, payload),
  (characters) =>
    view.log("incoming", "browser.clipboard.copy", { characters }),
).attach();

addressForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const value = elements.addressInput.value.trim();
  if (!value) return;
  void client.browser.nav
    .navigate({ url: normalizeUrl(value) })
    .catch(reportError);
});

newTabButton.addEventListener("click", () => {
  void client.browser.tab
    .create({ url: "about:blank" })
    .then((result) => {
      view.applyTabs(result.tabs);
      elements.addressInput.focus();
    })
    .catch(reportError);
});

clearLogsButton.addEventListener("click", () => view.clearLog());
void connect();

async function connect(): Promise<void> {
  try {
    await socketTransport.connect();
    elements.activeTabStatus.textContent = "Backend verbunden · Stream wartet";
    void receiveNotifications().catch(reportError);
    view.applyTabs((await client.browser.tab.list()).tabs);
  } catch (error) {
    reportError(error);
  }
}

async function receiveNotifications(): Promise<void> {
  for await (const notification of client.notifications()) {
    view.receive(notification.params);
  }
}

function normalizeUrl(value: string): string {
  return /^[a-z][a-z\d+.-]*:/i.test(value) ? value : `https://${value}`;
}

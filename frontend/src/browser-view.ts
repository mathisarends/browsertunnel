import type {
  BrowserEvent,
  CursorStyle as BrowserCursor,
  TabResult as BrowserTab,
} from "@browsertunnel/browser-rpc-client";

export type EventPayload = Record<string, unknown>;
export type LogDirection = "incoming" | "outgoing";

const MAX_LOG_ENTRIES = 200;
const KEPT_LOG_ENTRIES = 150;

export interface BrowserViewElements {
  canvas: HTMLCanvasElement;
  addressInput: HTMLInputElement;
  tabList: HTMLDivElement;
  activeTabStatus: HTMLSpanElement;
  cursorStatus: HTMLSpanElement;
  eventLog: HTMLOListElement;
  emptyLog: HTMLParagraphElement;
}

interface BrowserViewActions {
  activateTab(tabId: string): Promise<BrowserTab[]>;
  closeTab(tabId: string): Promise<BrowserTab[]>;
  reportError(error: unknown): void;
}

export class BrowserView {
  private tabs: BrowserTab[] = [];
  private latestFrame: string | undefined;
  private renderingFrame = false;
  private lastLoggedCursor: BrowserCursor | undefined;

  constructor(
    private readonly elements: BrowserViewElements,
    private readonly actions: BrowserViewActions,
  ) {}

  log(
    direction: LogDirection,
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
    this.elements.eventLog.append(entry);
    this.pruneLog();
    this.elements.emptyLog.hidden = true;
    this.elements.eventLog.scrollTop = this.elements.eventLog.scrollHeight;
  }

  clearLog(): void {
    this.elements.eventLog.replaceChildren();
    this.elements.emptyLog.hidden = false;
  }

  applyTabs(tabs: BrowserTab[]): void {
    this.tabs = tabs;
    const active = this.activeTab();
    if (active) {
      this.elements.addressInput.value =
        active.url === "about:blank" ? "" : active.url;
      this.elements.activeTabStatus.textContent =
        `${active.title || "Neuer Tab"} · verbunden`;
    }
    this.renderTabs();
  }

  receive(event: BrowserEvent): void {
    if (event.type === "browser.frame") {
      this.latestFrame = event.data;
      void this.renderLatestFrame().catch(this.actions.reportError);
      return;
    }

    if (event.type === "browser.cursor") {
      this.elements.canvas.style.cursor = event.cursor;
      this.elements.cursorStatus.textContent = `cursor: ${event.cursor}`;
      if (event.cursor !== this.lastLoggedCursor) {
        this.lastLoggedCursor = event.cursor;
        this.log("incoming", event.type, { cursor: event.cursor });
      }
      return;
    }

    this.log("incoming", event.type, event as unknown as EventPayload);
    switch (event.type) {
      case "browser.tabs":
        this.applyTabs(event.tabs);
        break;
      case "browser.navigation":
        this.applyNavigation(event);
        break;
      case "browser.targetCrashed":
        this.elements.activeTabStatus.textContent =
          `Browser abgestürzt · ${event.status}`;
        break;
    }
  }

  private activeTab(): BrowserTab | undefined {
    return this.tabs.find((tab) => tab.active);
  }

  private renderTabs(): void {
    this.elements.tabList.replaceChildren(
      ...this.tabs.map((tab) => this.createTabElement(tab)),
    );
  }

  private createTabElement(tab: BrowserTab): HTMLDivElement {
    const element = document.createElement("div");
    element.className = "browser-tab";
    element.role = "tab";
    element.tabIndex = tab.active ? 0 : -1;
    element.ariaSelected = String(tab.active);

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
      void this.actions
        .closeTab(tab.id)
        .then((tabs) => this.applyTabs(tabs))
        .catch(this.actions.reportError);
    });
    element.addEventListener("click", () => {
      void this.actions
        .activateTab(tab.id)
        .then((tabs) => this.applyTabs(tabs))
        .catch(this.actions.reportError);
    });
    element.append(favicon, title, close);
    return element;
  }

  private applyNavigation(
    event: Extract<BrowserEvent, { type: "browser.navigation" }>,
  ): void {
    this.tabs = this.tabs.map((tab) =>
      tab.id === event.tabId
        ? { ...tab, title: event.title, url: event.url }
        : tab,
    );
    if (this.activeTab()?.id === event.tabId) {
      this.elements.addressInput.value = event.url;
      this.elements.activeTabStatus.textContent =
        `${event.title || "Neuer Tab"} · ${event.loading ? "lädt" : "verbunden"}`;
    }
    this.renderTabs();
  }

  private async renderLatestFrame(): Promise<void> {
    if (this.renderingFrame) return;
    this.renderingFrame = true;
    try {
      while (this.latestFrame) {
        const encoded = this.latestFrame;
        this.latestFrame = undefined;
        const binary = atob(encoded);
        const bytes = Uint8Array.from(binary, (character) =>
          character.charCodeAt(0),
        );
        const bitmap = await createImageBitmap(
          new Blob([bytes], { type: "image/jpeg" }),
        );
        const { canvas } = this.elements;
        if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) {
          canvas.width = bitmap.width;
          canvas.height = bitmap.height;
        }
        canvas.getContext("2d")?.drawImage(bitmap, 0, 0);
        bitmap.close();
      }
    } finally {
      this.renderingFrame = false;
    }
  }

  private pruneLog(): void {
    const { eventLog } = this.elements;
    if (eventLog.childElementCount <= MAX_LOG_ENTRIES) return;
    const staleEntries = Array.from(eventLog.children).slice(
      0,
      eventLog.childElementCount - KEPT_LOG_ENTRIES,
    );
    for (const entry of staleEntries) entry.remove();
  }
}

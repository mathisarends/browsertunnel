import { ContextConsumer } from "@lit/context";
import { LitElement, html } from "lit";
import { live } from "lit/directives/live.js";
import { repeat } from "lit/directives/repeat.js";
import type {
  BrowserEvent,
  BrowserTunnelClient,
  TabResult,
} from "@browsertunnel/browser-rpc-client";
import { BrowserInput, MOUSE_METHOD } from "./browser-input";
import { browserSessionContext } from "./session-service";

type Navigation = Extract<BrowserEvent, { type: "browser.navigation" }>;
type Payload = Record<string, unknown>;
type LogEntry = {
  id: number;
  direction: "incoming" | "outgoing";
  name: string;
  time: string;
  payload: string;
};

export class BrowserPage extends LitElement {
  static properties = {
    tabs: { state: true },
    address: { state: true },
    status: { state: true },
    cursor: { state: true },
    logs: { state: true },
    navigation: { state: true },
  };

  private tabs: TabResult[] = [];
  private address = "https://example.com";
  private status = "Verbindung wird aufgebaut";
  private cursor = "default";
  private logs: LogEntry[] = [];
  private navigation = new Map<string, Navigation>();
  private readonly session = new ContextConsumer(this, {
    context: browserSessionContext,
    subscribe: true,
  });
  private client?: BrowserTunnelClient;
  private input?: BrowserInput;
  private connection?: AbortController;
  private nextLogId = 0;
  private latestFrame?: string;
  private renderingFrame = false;

  protected createRenderRoot(): HTMLElement {
    return this; // The application stylesheet is shared with the Canon root.
  }

  connectedCallback(): void {
    super.connectedCallback();
    this.connection = new AbortController();
    void this.connect(this.connection.signal);
  }

  disconnectedCallback(): void {
    this.connection?.abort();
    this.input?.detach();
    this.input = undefined;
    const client = this.client;
    this.client = undefined;
    void client?.close();
    this.latestFrame = undefined;
    super.disconnectedCallback();
  }

  private get canvas(): HTMLCanvasElement {
    return this.querySelector<HTMLCanvasElement>("#browser-canvas")!;
  }

  private get activeTab(): TabResult | undefined {
    return this.tabs.find((tab) => tab.active);
  }

  private async connect(signal: AbortSignal): Promise<void> {
    try {
      await this.updateComplete;
      if (signal.aborted) return;
      const service = this.session.value;
      if (!service) throw new Error("Browser session provider is missing");
      const client = await service.connect(signal, {
        request: (call, next) => {
          if (call.route.method !== MOUSE_METHOD) {
            this.log("outgoing", call.route.method, call.params as Payload);
          }
          return next();
        },
      });
      if (signal.aborted) {
        await client.close();
        return;
      }
      this.client = client;
      this.status = "Backend verbunden · Stream wartet";
      this.input = new BrowserInput(
        this.canvas,
        client,
        this.reportError,
        (payload) => this.log("outgoing", MOUSE_METHOD, payload),
        (characters) =>
          this.log("incoming", "browser.clipboard.copy", { characters }),
      );
      this.input.attach();
      void this.receive(client, signal);
      this.applyTabs((await client.browser.tab.list()).tabs);
    } catch (error) {
      if (!signal.aborted) this.reportError(error);
    }
  }

  private async receive(
    client: BrowserTunnelClient,
    signal: AbortSignal,
  ): Promise<void> {
    try {
      for await (const event of client.browser.event()) {
        if (signal.aborted) return;
        this.applyEvent(event);
      }
      if (!signal.aborted) this.status = "Verbindung geschlossen";
    } catch (error) {
      if (!signal.aborted) this.reportError(error);
    }
  }

  private applyTabs(tabs: TabResult[]): void {
    this.tabs = tabs;
    const active = this.activeTab;
    this.address = active?.url === "about:blank" ? "" : (active?.url ?? "");
    this.status = active
      ? `${active.title || "Neuer Tab"} · verbunden`
      : "Kein Tab geöffnet";
    const ids = new Set(tabs.map((tab) => tab.id));
    this.navigation = new Map(
      [...this.navigation].filter(([id]) => ids.has(id)),
    );
  }

  private applyEvent(event: BrowserEvent): void {
    if (event.type === "browser.frame") {
      this.latestFrame = event.data;
      void this.renderLatestFrame().catch(this.reportError);
      return;
    }
    if (event.type === "browser.cursor") {
      if (this.cursor !== event.cursor) {
        this.log("incoming", event.type, { cursor: event.cursor });
      }
      this.cursor = event.cursor;
      return;
    }
    this.log("incoming", event.type, event as unknown as Payload);
    switch (event.type) {
      case "browser.tabs":
        this.applyTabs(event.tabs);
        break;
      case "browser.navigation":
        this.navigation = new Map(this.navigation).set(event.tabId, event);
        this.tabs = this.tabs.map((tab) =>
          tab.id === event.tabId
            ? { ...tab, title: event.title, url: event.url }
            : tab,
        );
        if (this.activeTab?.id === event.tabId) {
          this.address = event.url === "about:blank" ? "" : event.url;
          this.status = `${event.title || "Neuer Tab"} · ${event.loading ? "lädt" : "verbunden"}`;
        }
        break;
      case "browser.targetCrashed":
        this.status = `Browser abgestürzt · ${event.status}`;
        break;
      case "browser.targetDetached":
        if (event.tabId === this.activeTab?.id) this.status = "Tab getrennt";
        break;
    }
  }

  private async renderLatestFrame(): Promise<void> {
    if (this.renderingFrame) return;
    this.renderingFrame = true;
    const signal = this.connection?.signal;
    try {
      while (this.latestFrame && !signal?.aborted) {
        const encoded = this.latestFrame;
        this.latestFrame = undefined;
        const bytes = Uint8Array.from(atob(encoded), (character) =>
          character.charCodeAt(0),
        );
        const bitmap = await createImageBitmap(
          new Blob([bytes], { type: "image/jpeg" }),
        );
        try {
          if (signal?.aborted) return;
          const canvas = this.canvas;
          if (
            canvas.width !== bitmap.width ||
            canvas.height !== bitmap.height
          ) {
            canvas.width = bitmap.width;
            canvas.height = bitmap.height;
          }
          canvas.getContext("2d")?.drawImage(bitmap, 0, 0);
        } finally {
          bitmap.close();
        }
      }
    } finally {
      this.renderingFrame = false;
    }
  }

  private readonly reportError = (error: unknown): void => {
    if (!this.isConnected) return;
    const message = error instanceof Error ? error.message : String(error);
    this.status = `Fehler · ${message}`;
    this.log("incoming", "client.error", { message });
  };

  private log(
    direction: LogEntry["direction"],
    name: string,
    payload: Payload = {},
  ): void {
    this.logs = [
      ...this.logs,
      {
        id: this.nextLogId++,
        direction,
        name,
        time: new Date().toLocaleTimeString("de-DE", { hour12: false }),
        payload: JSON.stringify(payload, null, 2),
      },
    ];
    if (this.logs.length > 200) this.logs = this.logs.slice(-150);
    void this.updateComplete.then(() => {
      const log = this.querySelector("#event-log");
      if (log) log.scrollTop = log.scrollHeight;
    });
  }

  private run(action: (client: BrowserTunnelClient) => Promise<unknown>): void {
    if (this.client) void action(this.client).catch(this.reportError);
  }

  private navigate(event: SubmitEvent): void {
    event.preventDefault();
    const value =
      this.querySelector<HTMLInputElement>("#address-input")!.value.trim();
    if (!value) return;
    const url = /^[a-z][a-z\d+.-]*:/i.test(value) ? value : `https://${value}`;
    this.run((client) => client.browser.nav.navigate({ url }));
  }

  private newTab(): void {
    this.run(async (client) => {
      this.applyTabs(
        (await client.browser.tab.create({ url: "about:blank" })).tabs,
      );
      await this.updateComplete;
      this.querySelector<HTMLInputElement>("#address-input")?.focus();
    });
  }

  private activateTab(tabId: string): void {
    this.run(async (client) =>
      this.applyTabs((await client.browser.tab.activate({ tabId })).tabs),
    );
  }

  private closeTab(event: Event, tabId: string): void {
    event.stopPropagation();
    this.run(async (client) =>
      this.applyTabs((await client.browser.tab.close({ tabId })).tabs),
    );
  }

  protected render() {
    const active = this.activeTab;
    const navigation = active ? this.navigation.get(active.id) : undefined;
    const loading = navigation?.loading ?? false;
    return html`
      <main class="workspace">
        <section class="browser-panel" aria-label="Browser-Vorschau">
          <header class="browser-chrome">
            <div class="tab-strip">
              <div class="window-controls" aria-hidden="true">
                <span></span><span></span><span></span>
              </div>
              <div class="tabs">
                <div
                  id="tab-list"
                  class="tab-list"
                  role="tablist"
                  aria-label="Browser-Tabs"
                >
                  ${repeat(
                    this.tabs,
                    (tab) => tab.id,
                    (tab) => html`
                      <div
                        class="browser-tab"
                        role="tab"
                        tabindex=${tab.active ? 0 : -1}
                        aria-selected=${String(tab.active)}
                        @click=${() => this.activateTab(tab.id)}
                        @keydown=${(event: KeyboardEvent) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            this.activateTab(tab.id);
                          }
                        }}
                      >
                        <i aria-hidden="true"></i
                        ><span>${tab.title || "Neuer Tab"}</span>
                        <button
                          type="button"
                          class="close-tab"
                          aria-label=${`${tab.title || "Neuer Tab"} schließen`}
                          @click=${(event: Event) => this.closeTab(event, tab.id)}
                        >
                          ×
                        </button>
                      </div>
                    `,
                  )}
                </div>
                <button
                  id="new-tab"
                  class="new-tab"
                  type="button"
                  aria-label="Neuen Tab öffnen"
                  @click=${this.newTab}
                >
                  +
                </button>
              </div>
            </div>
            <div class="browser-bar">
              <nav class="navigation-controls" aria-label="Seitennavigation">
                <button
                  id="nav-back"
                  type="button"
                  aria-label="Zurück"
                  ?disabled=${!navigation?.canGoBack}
                  @click=${() => this.run((client) => client.browser.nav.back())}
                >
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path d="m12.5 4.5-5.5 5 5.5 5" />
                  </svg>
                </button>
                <button
                  id="nav-forward"
                  type="button"
                  aria-label="Vor"
                  ?disabled=${!navigation?.canGoForward}
                  @click=${() => this.run((client) => client.browser.nav.forward())}
                >
                  <svg viewBox="0 0 20 20" aria-hidden="true">
                    <path d="m7.5 4.5 5.5 5-5.5 5" />
                  </svg>
                </button>
                <button
                  id="nav-reload"
                  type="button"
                  aria-label=${loading ? "Laden abbrechen" : "Neu laden"}
                  data-loading=${String(loading)}
                  ?disabled=${!active}
                  @click=${() => this.run((client) => (loading ? client.browser.nav.stop() : client.browser.nav.reload()))}
                >
                  <svg
                    class="reload-icon"
                    viewBox="0 0 20 20"
                    aria-hidden="true"
                  >
                    <path d="M15.3 7.1A6 6 0 1 0 16 10" />
                    <path d="M15.3 3.8v3.7H12" />
                  </svg>
                  <svg class="stop-icon" viewBox="0 0 20 20" aria-hidden="true">
                    <path d="M6 6h8v8H6z" />
                  </svg>
                </button>
              </nav>
              <form
                id="address-form"
                class="address-form"
                @submit=${this.navigate}
              >
                <label class="visually-hidden" for="address-input">URL</label>
                <input
                  id="address-input"
                  name="url"
                  type="text"
                  inputmode="url"
                  .value=${live(this.address)}
                  @input=${(event: InputEvent) => {
                    this.address = (event.target as HTMLInputElement).value;
                  }}
                  placeholder="URL eingeben"
                  autocomplete="url"
                  spellcheck="false"
                />
              </form>
            </div>
          </header>
          <canvas
            id="browser-canvas"
            width="1600"
            height="900"
            style=${`cursor: ${this.cursor}`}
            aria-label="Browser-Stream"
          ></canvas>
          <footer class="stream-status">
            <span
              ><i class="status-dot"></i
              ><span id="active-tab-status">${this.status}</span></span
            >
            <span
              ><span id="cursor-status">cursor: ${this.cursor}</span> · 1600 ×
              900</span
            >
          </footer>
        </section>
        <aside class="log-panel" aria-label="Event-Log">
          <header class="log-header">
            <div>
              <p class="eyebrow">Debug stream</p>
              <h1>Events</h1>
            </div>
            <button
              id="clear-logs"
              type="button"
              @click=${() => {
                this.logs = [];
              }}
            >
              Clear
            </button>
          </header>
          <div class="log-legend" aria-label="Event-Richtungen">
            <span><i class="outgoing-dot"></i>Frontend → Backend</span>
            <span><i class="incoming-dot"></i>Backend → Frontend</span>
          </div>
          <ol id="event-log" class="event-log" aria-live="polite">
            ${repeat(
              this.logs,
              (entry) => entry.id,
              (entry) => html`
                <li class=${`log-entry ${entry.direction}`}>
                  <div class="log-meta">
                    <span
                      >${entry.direction === "outgoing" ? "OUT" : "IN"}</span
                    >
                    <strong>${entry.name}</strong><time>${entry.time}</time>
                  </div>
                  <pre>${entry.payload}</pre>
                </li>
              `,
            )}
          </ol>
          <p id="empty-log" class="empty-log" ?hidden=${this.logs.length > 0}>
            Noch keine Events.
          </p>
        </aside>
      </main>
    `;
  }
}

customElements.define("browser-tunnel-page", BrowserPage);

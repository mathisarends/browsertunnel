const API_PREFIX = "/api";

export type BrowserTab = {
  id: string;
  title: string;
  url: string;
  active: boolean;
};

export type BrowserEvent =
  | { type: "browser.frame"; data: string }
  | { type: "browser.tabs"; tabs: BrowserTab[] }
  | {
      type: "browser.navigation";
      tabId: string;
      title: string;
      url: string;
      loading: boolean;
      canGoBack: boolean;
      canGoForward: boolean;
      error: string | null;
    }
  | { type: "browser.targetCrashed"; tabId: string; status: string; errorCode: number }
  | { type: "browser.targetDetached"; tabId: string | null };

type PendingRequest = {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
};

/** Minimal JSON-RPC client for the browser WebSocket. */
export class BrowserClient {
  private socket: WebSocket | undefined;
  private nextId = 1;
  private pending = new Map<number, PendingRequest>();

  constructor(private onEvent: (event: BrowserEvent) => void) {}

  connect(): Promise<void> {
    const url = new URL("/api/browser/ws", window.location.href);
    url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    this.socket = new WebSocket(url);
    this.socket.addEventListener("message", (message) => this.handleMessage(message));
    this.socket.addEventListener("close", () => {
      for (const request of this.pending.values()) {
        request.reject(new Error("Backend connection closed"));
      }
      this.pending.clear();
    });

    return new Promise((resolve, reject) => {
      this.socket?.addEventListener("open", () => resolve(), { once: true });
      this.socket?.addEventListener("error", () => reject(new Error("Backend connection failed")), {
        once: true,
      });
    });
  }

  call<T = Record<string, never>>(method: string, params: object = {}): Promise<T> {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("Backend is not connected"));
    }

    const id = this.nextId++;
    this.socket.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: resolve as (value: unknown) => void, reject });
    });
  }

  private handleMessage(message: MessageEvent): void {
    const payload = JSON.parse(String(message.data));
    if (payload.method === "browser.event") {
      this.onEvent(payload.params as BrowserEvent);
      return;
    }

    const request = this.pending.get(payload.id);
    if (!request) return;
    this.pending.delete(payload.id);
    if (payload.error) {
      request.reject(new Error(`${payload.error.message} (${payload.error.code})`));
    } else {
      request.resolve(payload.result);
    }
  }
}

/** Calls the separately running backend through Vite's development proxy. */
export async function getJson<T>(path: string): Promise<T> {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const response = await fetch(`${API_PREFIX}${normalizedPath}`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as T;
}

import { RpcRemoteError, type RpcTransport } from "./transport";

type PendingRequest = {
  resolve(value: unknown): void;
  reject(error: Error): void;
};

type QueueWaiter = {
  resolve(result: IteratorResult<unknown>): void;
  reject(error: Error): void;
};

class NotificationQueue implements AsyncIterable<unknown> {
  private readonly values: unknown[] = [];
  private readonly waiters: QueueWaiter[] = [];
  private finished = false;
  private failure: Error | undefined;

  push(value: unknown): void {
    if (this.finished) return;
    const waiter = this.waiters.shift();
    if (waiter) waiter.resolve({ done: false, value });
    else this.values.push(value);
  }

  end(error?: Error): void {
    if (this.finished) return;
    this.finished = true;
    this.failure = error;
    for (const waiter of this.waiters.splice(0)) {
      if (error) waiter.reject(error);
      else waiter.resolve({ done: true, value: undefined });
    }
  }

  [Symbol.asyncIterator](): AsyncIterator<unknown> {
    return {
      next: () => {
        const value = this.values.shift();
        if (value !== undefined) return Promise.resolve({ done: false, value });
        if (this.failure) return Promise.reject(this.failure);
        if (this.finished) return Promise.resolve({ done: true, value: undefined });
        return new Promise((resolve, reject) => this.waiters.push({ resolve, reject }));
      },
    };
  }
}

export class WebSocketRpcTransport implements RpcTransport {
  private socket: WebSocket | undefined;
  private nextId = 1;
  private readonly pending = new Map<number, PendingRequest>();
  private readonly notificationQueue = new NotificationQueue();

  constructor(private readonly url: string | URL) {}

  connect(): Promise<void> {
    if (this.socket) return Promise.reject(new Error("Transport is already connected"));

    const socket = new WebSocket(this.url);
    this.socket = socket;
    socket.addEventListener("message", (event) => this.handleMessage(event));
    socket.addEventListener("close", (event) => this.handleClose(event));

    return new Promise((resolve, reject) => {
      socket.addEventListener("open", () => resolve(), { once: true });
      socket.addEventListener(
        "error",
        () => reject(new Error("RPC connection failed")),
        { once: true },
      );
    });
  }

  request<TResult>(method: string, params: object): Promise<TResult> {
    if (this.socket?.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("RPC transport is not connected"));
    }

    const id = this.nextId++;
    this.socket.send(JSON.stringify({ jsonrpc: "2.0", id, method, params }));
    return new Promise<TResult>((resolve, reject) => {
      this.pending.set(id, {
        resolve: (value) => resolve(value as TResult),
        reject,
      });
    });
  }

  notifications(): AsyncIterable<unknown> {
    return this.notificationQueue;
  }

  close(): Promise<void> {
    const socket = this.socket;
    if (!socket || socket.readyState === WebSocket.CLOSED) return Promise.resolve();
    if (socket.readyState === WebSocket.CLOSING) {
      return new Promise((resolve) => socket.addEventListener("close", () => resolve(), { once: true }));
    }
    return new Promise((resolve) => {
      socket.addEventListener("close", () => resolve(), { once: true });
      socket.close(1000, "Client closed");
    });
  }

  private handleMessage(event: MessageEvent): void {
    let payload: unknown;
    try {
      payload = JSON.parse(String(event.data));
    } catch {
      return;
    }
    if (!isRecord(payload)) return;

    if (typeof payload.method === "string" && !("id" in payload)) {
      this.notificationQueue.push(payload);
      return;
    }
    if (typeof payload.id !== "number") return;

    const request = this.pending.get(payload.id);
    if (!request) return;
    this.pending.delete(payload.id);

    if (isRecord(payload.error)) {
      request.reject(
        new RpcRemoteError(
          typeof payload.error.code === "number" ? payload.error.code : -32603,
          typeof payload.error.message === "string" ? payload.error.message : "Unknown RPC error",
          payload.error.data,
        ),
      );
      return;
    }
    request.resolve(payload.result);
  }

  private handleClose(event: CloseEvent): void {
    const clean = event.code === 1000;
    const error = new Error(
      clean ? "RPC connection closed" : `RPC connection closed unexpectedly (${event.code})`,
    );
    for (const request of this.pending.values()) request.reject(error);
    this.pending.clear();
    this.notificationQueue.end(clean ? undefined : error);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

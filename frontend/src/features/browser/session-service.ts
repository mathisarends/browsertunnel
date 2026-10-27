import { createContext } from "@lit/context";
import {
  BrowserTunnelClient,
  WebSocketTransport,
  type RpcClientMiddleware,
} from "@browsertunnel/browser-rpc-client";

export class BrowserSessionService {
  async connect(
    signal: AbortSignal,
    middleware: RpcClientMiddleware,
  ): Promise<BrowserTunnelClient> {
    const url = new URL("/api/browser/ws", window.location.href);
    url.protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const transport = await WebSocketTransport.open(url, {
      signal,
      heartbeatIntervalMs: 30_000,
      heartbeatTimeoutMs: 10_000,
    });
    if (signal.aborted) {
      await transport.close();
      throw signal.reason;
    }
    let pending: Promise<unknown> = Promise.resolve();
    const ordered: RpcClientMiddleware = {
      request(_call, next) {
        const response = pending.then(next);
        pending = response.then(
          () => undefined,
          () => undefined,
        );
        return response;
      },
    };
    return new BrowserTunnelClient(transport, {
      middleware: [ordered, middleware],
    });
  }
}

export const browserSessionContext = createContext<BrowserSessionService>(
  Symbol("browser-session"),
);

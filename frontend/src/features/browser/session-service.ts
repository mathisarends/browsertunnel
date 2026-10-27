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
    const transport = await WebSocketTransport.open(url, { signal });
    if (signal.aborted) {
      await transport.close();
      throw signal.reason;
    }
    return new BrowserTunnelClient(transport, { middleware: [middleware] });
  }
}

export const browserSessionContext = createContext<BrowserSessionService>(
  Symbol("browser-session"),
);

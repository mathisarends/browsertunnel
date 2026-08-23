// Generated from openrpc.json. Do not edit manually.

import { RpcMethod } from "./models";
import type {
  BrowserEventNotification,
  ClickParams,
  ClipboardResult,
  CreateTabParams,
  HoverParams,
  KeyParams,
  NavigateParams,
  ReloadParams,
  ScrollParams,
  TabParams,
  TabsResult,
  TextParams,
} from "./models";
import type { RpcTransport } from "../transport";

class BrowserNavClient {
  constructor(private readonly transport: RpcTransport) {}

  async navigate(params: NavigateParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_NAV_NAVIGATE,
      params,
    );
  }

  async back(): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_NAV_BACK,
    );
  }

  async forward(): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_NAV_FORWARD,
    );
  }

  async reload(params: ReloadParams = {}): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_NAV_RELOAD,
      params,
    );
  }

  async stop(): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_NAV_STOP,
    );
  }
}

class BrowserInputClient {
  constructor(private readonly transport: RpcTransport) {}

  async click(params: ClickParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_INPUT_CLICK,
      params,
    );
  }

  async hover(params: HoverParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_INPUT_HOVER,
      params,
    );
  }

  async scroll(params: ScrollParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_INPUT_SCROLL,
      params,
    );
  }

  async key(params: KeyParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_INPUT_KEY,
      params,
    );
  }

  async paste(params: TextParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_INPUT_PASTE,
      params,
    );
  }
}

class BrowserInputTextClient {
  constructor(private readonly transport: RpcTransport) {}

  async insert(params: TextParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_INPUT_TEXT_INSERT,
      params,
    );
  }
}

class BrowserClipboardClient {
  constructor(private readonly transport: RpcTransport) {}

  read(): Promise<ClipboardResult> {
    return this.transport.request<ClipboardResult>(
      RpcMethod.BROWSER_CLIPBOARD_READ,
    );
  }

  async write(params: TextParams): Promise<void> {
    await this.transport.request<null>(
      RpcMethod.BROWSER_CLIPBOARD_WRITE,
      params,
    );
  }
}

class BrowserTabClient {
  constructor(private readonly transport: RpcTransport) {}

  list(): Promise<TabsResult> {
    return this.transport.request<TabsResult>(
      RpcMethod.BROWSER_TAB_LIST,
    );
  }

  create(params: CreateTabParams = {}): Promise<TabsResult> {
    return this.transport.request<TabsResult>(
      RpcMethod.BROWSER_TAB_CREATE,
      params,
    );
  }

  activate(params: TabParams): Promise<TabsResult> {
    return this.transport.request<TabsResult>(
      RpcMethod.BROWSER_TAB_ACTIVATE,
      params,
    );
  }

  close(params: TabParams): Promise<TabsResult> {
    return this.transport.request<TabsResult>(
      RpcMethod.BROWSER_TAB_CLOSE,
      params,
    );
  }
}

export class BrowserTunnelClient {
  readonly browser;

  constructor(private readonly transport: RpcTransport) {
    this.browser = {
      nav: new BrowserNavClient(this.transport),
      input: Object.assign(new BrowserInputClient(this.transport), {
        text: new BrowserInputTextClient(this.transport),
      } as const),
      clipboard: new BrowserClipboardClient(this.transport),
      tab: new BrowserTabClient(this.transport),
    } as const;
  }

  async *notifications(): AsyncIterable<BrowserEventNotification> {
    for await (const message of this.transport.notifications()) {
      yield message as BrowserEventNotification;
    }
  }

  close(): Promise<void> {
    return this.transport.close();
  }
}

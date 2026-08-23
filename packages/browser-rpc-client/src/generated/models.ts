// Generated from openrpc.json. Do not edit manually.

export const RpcMethod = {
  BROWSER_NAV_NAVIGATE: "browser.nav.navigate",
  BROWSER_NAV_BACK: "browser.nav.back",
  BROWSER_NAV_FORWARD: "browser.nav.forward",
  BROWSER_NAV_RELOAD: "browser.nav.reload",
  BROWSER_NAV_STOP: "browser.nav.stop",
  BROWSER_INPUT_CLICK: "browser.input.click",
  BROWSER_INPUT_HOVER: "browser.input.hover",
  BROWSER_INPUT_SCROLL: "browser.input.scroll",
  BROWSER_INPUT_KEY: "browser.input.key",
  BROWSER_INPUT_TEXT_INSERT: "browser.input.text.insert",
  BROWSER_INPUT_PASTE: "browser.input.paste",
  BROWSER_CLIPBOARD_COPY: "browser.clipboard.copy",
  BROWSER_CLIPBOARD_READ: "browser.clipboard.read",
  BROWSER_CLIPBOARD_WRITE: "browser.clipboard.write",
  BROWSER_TAB_LIST: "browser.tab.list",
  BROWSER_TAB_CREATE: "browser.tab.create",
  BROWSER_TAB_ACTIVATE: "browser.tab.activate",
  BROWSER_TAB_CLOSE: "browser.tab.close",
} as const;

export type RpcMethod = (typeof RpcMethod)[keyof typeof RpcMethod];

export type BrowserCursorEvent = {
  type: "browser.cursor";
  tabId: string;
  cursor: CursorStyle;
};

export type BrowserFrameEvent = {
  type: "browser.frame";
  data: string;
};

export type BrowserNavigationEvent = {
  type: "browser.navigation";
  tabId: string;
  title: string;
  url: string;
  loading: boolean;
  canGoBack: boolean;
  canGoForward: boolean;
  error?: string | null;
};

export type BrowserTabsEvent = {
  type: "browser.tabs";
  tabs: TabResult[];
};

export type BrowserTargetCrashedEvent = {
  type: "browser.targetCrashed";
  tabId: string;
  status: string;
  errorCode: number;
};

export type BrowserTargetDetachedEvent = {
  type: "browser.targetDetached";
  tabId: string | null;
};

export const ClickEventType = {
  MOUSEPRESSED: "mousePressed",
  MOUSERELEASED: "mouseReleased",
} as const;

export type ClickEventType = (typeof ClickEventType)[keyof typeof ClickEventType];

export type ClickParams = {
  type: ClickEventType;
  x: number;
  y: number;
  button: "left" | "middle" | "right" | "back" | "forward";
  buttons: number;
  modifiers?: number;
  clickCount?: number;
};

export type ClipboardResult = {
  text: string;
};

export type CreateTabParams = {
  url?: string;
};

export const CursorStyle = {
  DEFAULT: "default",
  NONE: "none",
  CONTEXT_MENU: "context-menu",
  HELP: "help",
  POINTER: "pointer",
  PROGRESS: "progress",
  WAIT: "wait",
  CELL: "cell",
  CROSSHAIR: "crosshair",
  TEXT: "text",
  VERTICAL_TEXT: "vertical-text",
  ALIAS: "alias",
  COPY: "copy",
  MOVE: "move",
  NO_DROP: "no-drop",
  NOT_ALLOWED: "not-allowed",
  GRAB: "grab",
  GRABBING: "grabbing",
  ALL_SCROLL: "all-scroll",
  COL_RESIZE: "col-resize",
  ROW_RESIZE: "row-resize",
  N_RESIZE: "n-resize",
  E_RESIZE: "e-resize",
  S_RESIZE: "s-resize",
  W_RESIZE: "w-resize",
  NE_RESIZE: "ne-resize",
  NW_RESIZE: "nw-resize",
  SE_RESIZE: "se-resize",
  SW_RESIZE: "sw-resize",
  EW_RESIZE: "ew-resize",
  NS_RESIZE: "ns-resize",
  NESW_RESIZE: "nesw-resize",
  NWSE_RESIZE: "nwse-resize",
  ZOOM_IN: "zoom-in",
  ZOOM_OUT: "zoom-out",
} as const;

export type CursorStyle = (typeof CursorStyle)[keyof typeof CursorStyle];

export type HoverParams = {
  x: number;
  y: number;
  buttons?: number;
  modifiers?: number;
};

export const KeyEventType = {
  KEYDOWN: "keyDown",
  KEYUP: "keyUp",
  RAWKEYDOWN: "rawKeyDown",
  CHAR: "char",
} as const;

export type KeyEventType = (typeof KeyEventType)[keyof typeof KeyEventType];

export type KeyParams = {
  type: KeyEventType;
  key: string;
  code?: string;
  text?: string | null;
  modifiers?: number;
  autoRepeat?: boolean;
};

export type NavigateParams = {
  url: string;
};

export type ReloadParams = {
  ignoreCache?: boolean;
};

export type ScrollParams = {
  x: number;
  y: number;
  deltaX: number;
  deltaY: number;
};

export type TabParams = {
  tabId: string;
};

export type TabResult = {
  id: string;
  title: string;
  url: string;
  active: boolean;
};

export type TabsResult = {
  tabs: TabResult[];
};

export type TextParams = {
  text: string;
};

export type BrowserEventNotification = {
  jsonrpc: "2.0";
  method: "browser.event";
  params: BrowserEvent;
};

export type BrowserEvent = BrowserFrameEvent | BrowserTabsEvent | BrowserNavigationEvent | BrowserCursorEvent | BrowserTargetCrashedEvent | BrowserTargetDetachedEvent;

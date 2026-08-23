import type {
  BrowserTunnelClient,
  MouseParams,
} from "@browsertunnel/browser-rpc-client";

export const MOUSE_METHOD = "browser.input.mouse";

type MousePoint = Pick<MouseParams, "x" | "y">;
type ReportError = (error: unknown) => void;

const MOUSE_LOG_IDLE_MS = 250;
const MOUSE_BUTTONS = ["left", "middle", "right", "back", "forward"] as const;

export class BrowserInput {
  private latestMove?: MouseParams;
  private animationFrame?: number;
  private inputQueue: Promise<void> = Promise.resolve();
  private logTimer?: ReturnType<typeof setTimeout>;
  private logStart?: MousePoint;
  private logEnd?: MousePoint;
  private logMoves = 0;
  private lastPoint?: MousePoint;
  private readonly pressedButtons = new Map<number, MouseParams["button"]>();

  constructor(
    private readonly canvas: HTMLCanvasElement,
    private readonly client: BrowserTunnelClient,
    private readonly reportError: ReportError,
    private readonly logMovement: (
      payload: { from: MousePoint; to: MousePoint; moves: number },
    ) => void,
    private readonly logClipboardCopy: (characters: number) => void,
  ) {}

  attach(): void {
    this.canvas.tabIndex = 0;
    this.canvas.addEventListener("mousedown", this.onMouseDown);
    this.canvas.addEventListener("mousemove", this.onCanvasMouseMove);
    this.canvas.addEventListener("mouseleave", this.onCanvasMouseMove);
    this.canvas.addEventListener("contextmenu", preventDefault);
    this.canvas.addEventListener("wheel", this.onWheel, { passive: false });
    this.canvas.addEventListener("keydown", this.onKeyDown);
    this.canvas.addEventListener("keyup", this.onKeyUp);
    window.addEventListener("mouseup", this.onMouseUp);
    window.addEventListener("mousemove", this.onWindowMouseMove);
    window.addEventListener("blur", this.releaseButtons);
    document.addEventListener("paste", this.onPaste);
  }

  private readonly onMouseDown = (event: MouseEvent): void => {
    event.preventDefault();
    this.canvas.focus();
    const button = mouseButton(event.button);
    this.pressedButtons.set(event.button, button);
    this.flushMove();
    this.enqueueMouse({
      type: "mouseDown",
      ...this.point(event),
      button,
      buttons: event.buttons,
      modifiers: modifiers(event),
      clickCount: event.detail,
    });
  };

  private readonly onMouseUp = (event: MouseEvent): void => {
    const button = this.pressedButtons.get(event.button);
    if (button === undefined) return;
    event.preventDefault();
    this.flushMove();
    this.enqueueMouse({
      type: "mouseUp",
      ...this.point(event),
      button,
      buttons: event.buttons,
      modifiers: modifiers(event),
      clickCount: event.detail,
    });
    this.pressedButtons.delete(event.button);
  };

  private readonly onCanvasMouseMove = (event: MouseEvent): void => {
    if (this.pressedButtons.size === 0) this.forwardMove(event);
  };

  private readonly onWindowMouseMove = (event: MouseEvent): void => {
    if (this.pressedButtons.size > 0) this.forwardMove(event);
  };

  private readonly releaseButtons = (): void => {
    if (this.pressedButtons.size === 0) return;
    this.flushMove();
    const point = this.lastPoint ?? { x: 0, y: 0 };
    for (const button of this.pressedButtons.values()) {
      this.enqueueMouse({
        type: "mouseUp",
        ...point,
        button,
        buttons: 0,
        clickCount: 0,
      });
    }
    this.pressedButtons.clear();
  };

  private readonly onWheel = (event: WheelEvent): void => {
    event.preventDefault();
    void this.client.browser.input
      .scroll({
        ...this.point(event),
        deltaX: event.deltaX,
        deltaY: event.deltaY,
      })
      .catch(this.reportError);
  };

  private readonly onPaste = (event: ClipboardEvent): void => {
    if (document.activeElement !== this.canvas) return;
    event.preventDefault();
    const text = event.clipboardData?.getData("text/plain");
    if (text) void this.client.browser.input.paste({ text }).catch(this.reportError);
  };

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    // Allow the browser to produce a paste event that contains the clipboard.
    if (isShortcut(event, "v")) return;
    if (isShortcut(event, "c")) {
      event.preventDefault();
      void this.copyFromPage().catch(this.reportError);
      return;
    }
    event.preventDefault();
    this.sendKey(event, keyText(event) === undefined ? "rawKeyDown" : "keyDown");
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => {
    if (isShortcut(event, "v") || isShortcut(event, "c")) return;
    event.preventDefault();
    this.sendKey(event, "keyUp");
  };

  private point(event: MouseEvent | WheelEvent): MousePoint {
    const bounds = this.canvas.getBoundingClientRect();
    return {
      x: ((event.clientX - bounds.left) / bounds.width) * this.canvas.width,
      y: ((event.clientY - bounds.top) / bounds.height) * this.canvas.height,
    };
  }

  private forwardMove(event: MouseEvent): void {
    const move: MouseParams = {
      type: "mouseMove",
      ...this.point(event),
      button: this.pressedButtons.values().next().value ?? "none",
      buttons: event.buttons,
      modifiers: modifiers(event),
      clickCount: 0,
    };
    this.documentMove(move);
    this.latestMove = move;
    this.animationFrame ??= requestAnimationFrame(this.flushMove);
  }

  private readonly flushMove = (): void => {
    if (this.animationFrame !== undefined) cancelAnimationFrame(this.animationFrame);
    this.animationFrame = undefined;
    const move = this.latestMove;
    this.latestMove = undefined;
    if (move) this.enqueueMouse(move);
  };

  private enqueueMouse(params: MouseParams): void {
    this.inputQueue = this.inputQueue
      .then(() => this.client.browser.input.mouse(params))
      .catch(this.reportError);
  }

  private documentMove(params: MouseParams): void {
    const point = { x: params.x, y: params.y };
    this.logStart ??= this.lastPoint ?? point;
    this.logEnd = point;
    this.logMoves += 1;
    this.lastPoint = point;
    if (this.logTimer !== undefined) clearTimeout(this.logTimer);
    this.logTimer = setTimeout(() => {
      this.logTimer = undefined;
      if (!this.logStart || !this.logEnd) return;
      this.logMovement({
        from: this.logStart,
        to: this.logEnd,
        moves: this.logMoves,
      });
      this.logStart = undefined;
      this.logEnd = undefined;
      this.logMoves = 0;
    }, MOUSE_LOG_IDLE_MS);
  }

  private sendKey(
    event: KeyboardEvent,
    type: "rawKeyDown" | "keyDown" | "keyUp",
  ): void {
    const virtualKeyCode = windowsVirtualKeyCode(event);
    const text = type === "keyDown" ? keyText(event) : undefined;
    void this.client.browser.input
      .key({
        type,
        key: event.key,
        code: event.code,
        text,
        unmodifiedText: text,
        modifiers: modifiers(event),
        autoRepeat: event.repeat,
        windowsVirtualKeyCode: virtualKeyCode,
        nativeVirtualKeyCode: virtualKeyCode,
        location: event.location,
        isKeypad: event.location === KeyboardEvent.DOM_KEY_LOCATION_NUMPAD,
        isSystemKey: event.altKey,
      })
      .catch(this.reportError);
  }

  private async copyFromPage(): Promise<void> {
    const { text } = await this.client.browser.clipboard.copy();
    if (!text) return;
    await navigator.clipboard.writeText(text);
    this.logClipboardCopy(text.length);
  }
}

function preventDefault(event: Event): void {
  event.preventDefault();
}

function mouseButton(button: number): MouseParams["button"] {
  return MOUSE_BUTTONS[button] ?? "none";
}

function modifiers(event: MouseEvent | KeyboardEvent): number {
  return Number(event.altKey) + Number(event.ctrlKey) * 2 +
    Number(event.metaKey) * 4 + Number(event.shiftKey) * 8;
}

function isShortcut(event: KeyboardEvent, key: string): boolean {
  return (event.ctrlKey || event.metaKey) && !event.altKey &&
    event.key.toLowerCase() === key;
}

const VIRTUAL_KEY: Readonly<Record<string, number>> = {
  Backspace: 8, Tab: 9, Enter: 13, NumpadEnter: 13, ShiftLeft: 16,
  ShiftRight: 16, ControlLeft: 17, ControlRight: 17, AltLeft: 18,
  AltRight: 18, Pause: 19, CapsLock: 20, Escape: 27, Space: 32,
  PageUp: 33, PageDown: 34, End: 35, Home: 36, ArrowLeft: 37,
  ArrowUp: 38, ArrowRight: 39, ArrowDown: 40, Insert: 45, Delete: 46,
  MetaLeft: 91, MetaRight: 92, ContextMenu: 93, NumpadMultiply: 106,
  NumpadAdd: 107, NumpadSubtract: 109, NumpadDecimal: 110,
  NumpadDivide: 111, NumLock: 144, ScrollLock: 145, Semicolon: 186,
  Equal: 187, Comma: 188, Minus: 189, Period: 190, Slash: 191,
  Backquote: 192, BracketLeft: 219, Backslash: 220, BracketRight: 221,
  Quote: 222,
};

function windowsVirtualKeyCode(event: KeyboardEvent): number {
  const mapped = VIRTUAL_KEY[event.code];
  if (mapped !== undefined) return mapped;
  if (/^Key[A-Z]$/.test(event.code)) return event.code.charCodeAt(3);
  if (/^Digit[0-9]$/.test(event.code)) return event.code.charCodeAt(5);
  if (/^Numpad[0-9]$/.test(event.code)) return 96 + Number(event.code.at(-1));
  if (/^F(?:[1-9]|1[0-9]|2[0-4])$/.test(event.code)) {
    return 111 + Number(event.code.slice(1));
  }
  return event.keyCode;
}

function keyText(event: KeyboardEvent): string | undefined {
  const hasAccelerator = event.altKey || event.ctrlKey || event.metaKey;
  if (event.key === "Enter" && !hasAccelerator) return "\r";
  if (
    event.key.length === 1 &&
    (!hasAccelerator || event.getModifierState("AltGraph"))
  ) return event.key;
  return undefined;
}

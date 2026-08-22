import "./style.css";

type EventDirection = "incoming" | "outgoing";
type EventPayload = Record<string, unknown>;

function requireElement<T extends Element>(selector: string): T {
  const element = document.querySelector<T>(selector);

  if (!element) {
    throw new Error(`Required element not found: ${selector}`);
  }

  return element;
}

const canvas = requireElement<HTMLCanvasElement>("#browser-canvas");
const addressForm = requireElement<HTMLFormElement>("#address-form");
const addressInput = requireElement<HTMLInputElement>("#address-input");
const eventLog = requireElement<HTMLOListElement>("#event-log");
const emptyLog = requireElement<HTMLParagraphElement>("#empty-log");
const clearLogsButton = requireElement<HTMLButtonElement>("#clear-logs");

function formatPayload(payload: EventPayload): string {
  return JSON.stringify(payload, null, 2);
}

function appendEvent(direction: EventDirection, name: string, payload: EventPayload): void {
  const entry = document.createElement("li");
  entry.className = `log-entry ${direction}`;

  const meta = document.createElement("div");
  meta.className = "log-meta";

  const directionLabel = document.createElement("span");
  directionLabel.textContent = direction === "outgoing" ? "OUT" : "IN";

  const eventName = document.createElement("strong");
  eventName.textContent = name;

  const timestamp = document.createElement("time");
  timestamp.textContent = new Date().toLocaleTimeString("de-DE", { hour12: false });

  const payloadElement = document.createElement("pre");
  payloadElement.textContent = formatPayload(payload);

  meta.append(directionLabel, eventName, timestamp);
  entry.append(meta, payloadElement);
  eventLog.append(entry);
  emptyLog.hidden = true;
  eventLog.scrollTop = eventLog.scrollHeight;
}

addressForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const url = addressInput.value.trim();
  if (url) {
    recordOutgoingEvent("navigate", { url });
  }
});

clearLogsButton.addEventListener("click", () => {
  eventLog.replaceChildren();
  emptyLog.hidden = false;
});

export function recordOutgoingEvent(name: string, payload: EventPayload = {}): void {
  appendEvent("outgoing", name, payload);
}

export function recordIncomingEvent(name: string, payload: EventPayload = {}): void {
  appendEvent("incoming", name, payload);
}

// A future framecast client can draw decoded frames into this canvas.
export function drawFrame(frame: CanvasImageSource): void {
  const context = canvas.getContext("2d");
  context?.drawImage(frame, 0, 0, canvas.width, canvas.height);
}

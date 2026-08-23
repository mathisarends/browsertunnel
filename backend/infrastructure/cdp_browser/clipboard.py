import json
import logging

from backend.application import BrowserClipboard
from backend.infrastructure.cdp_browser.active_target import ActiveTarget

logger = logging.getLogger(__name__)

_CONTROL_MODIFIER = 2
_VIRTUAL_KEY_C = 67

_SELECTION_SOURCE = """
() => {
  const active = document.activeElement;
  const start = active && "selectionStart" in active ? active.selectionStart : null;
  if (start !== null && start !== active.selectionEnd) {
    return active.value.slice(start, active.selectionEnd);
  }
  return String(document.getSelection() ?? "");
}
"""

_COPY_SOURCE = """
(text) => {
  const active = document.activeElement;
  const selection = document.getSelection();
  const ranges = [];
  for (let i = 0; selection && i < selection.rangeCount; i += 1) {
    ranges.push(selection.getRangeAt(i));
  }
  const start = active && "selectionStart" in active ? active.selectionStart : null;
  const end = active && "selectionEnd" in active ? active.selectionEnd : null;

  const carrier = document.createElement("textarea");
  carrier.value = text;
  carrier.setAttribute(
    "style",
    "position:fixed;top:0;left:0;width:1px;height:1px;opacity:0",
  );
  document.body.append(carrier);
  carrier.select();
  let copied = false;
  try {
    copied = document.execCommand("copy");
  } finally {
    carrier.remove();
  }

  if (active && active.focus) active.focus();
  if (start !== null && active.setSelectionRange) {
    active.setSelectionRange(start, end);
  } else if (selection && ranges.length) {
    selection.removeAllRanges();
    for (const range of ranges) selection.addRange(range);
  }
  return copied;
}
"""


class ClipboardUnavailableError(RuntimeError):
    """Raised when the page refuses to hand over or accept clipboard text."""


class CdpClipboard(BrowserClipboard):
    def __init__(self, target: ActiveTarget) -> None:
        self._target = target

    async def copy(self) -> str:
        """Run the page's own copy command and hand the copied text back.

        The shortcut is dispatched as an ordinary raw key event. The page clipboard
        is authoritative afterwards, but reading it can be denied, so the raw
        selection serves as a fallback.
        """
        session = self._target.session()
        for event_type in ("rawKeyDown", "keyUp"):
            await session.input.dispatch_key_event(
                type=event_type,
                key="c",
                code="KeyC",
                modifiers=_CONTROL_MODIFIER,
                windows_virtual_key_code=_VIRTUAL_KEY_C,
                native_virtual_key_code=_VIRTUAL_KEY_C,
            )
        try:
            copied = await self.read()
        except RuntimeError:
            logger.debug("Clipboard read was denied; falling back to the selection")
            copied = ""
        return copied or await self._selection_text()

    async def read(self) -> str:
        result = await self._target.session().runtime.evaluate(
            expression="navigator.clipboard.readText()",
            await_promise=True,
            return_by_value=True,
            user_gesture=True,
        )
        if result.exception_details is not None:
            raise RuntimeError("The page denied clipboard read access")
        return str(result.result.value or "")

    async def write(self, text: str) -> None:
        result = await self._target.session().runtime.evaluate(
            expression=f"({_COPY_SOURCE})({json.dumps(text)})",
            return_by_value=True,
            user_gesture=True,
        )
        if result.exception_details is not None or not result.result.value:
            raise ClipboardUnavailableError("The page denied clipboard write access")

    async def _selection_text(self) -> str:
        result = await self._target.session().runtime.evaluate(
            expression=f"({_SELECTION_SOURCE})()",
            return_by_value=True,
        )
        if result.exception_details is not None:
            return ""
        return str(result.result.value or "")

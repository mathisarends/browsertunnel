import asyncio
import logging
from contextlib import suppress

from cdpify import CDPSession
from cdpify.domains.runtime.events import BindingCalledEvent, RuntimeEvent

from backend.application import CursorChanged, CursorStyle
from backend.infrastructure.events import EventBus

logger = logging.getLogger(__name__)

BINDING_NAME = "__browserTunnelCursor"
ISOLATED_WORLD = "browsertunnel:cursor"

_OBSERVER_SOURCE = """
(() => {
  const report = window.__BINDING__;
  if (typeof report !== "function") return;

  let reported = null;
  const publish = (cursor) => {
    if (cursor === reported) return;
    reported = cursor;
    report(cursor);
  };

  const range = document.createRange();
  const overText = (element, x, y) => {
    for (const node of element.childNodes) {
      if (node.nodeType !== Node.TEXT_NODE || !node.nodeValue.trim()) continue;
      range.selectNodeContents(node);
      for (const rect of range.getClientRects()) {
        if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
          return true;
        }
      }
    }
    return false;
  };

  const resolve = (x, y) => {
    const hit = document.elementFromPoint(x, y);
    if (!hit) return "default";

    for (let element = hit; element; element = element.parentElement) {
      const cursor = getComputedStyle(element).cursor;
      if (cursor && cursor !== "auto") return cursor;
    }
    return hit.isContentEditable || overText(hit, x, y) ? "text" : "default";
  };

  addEventListener(
    "mousemove",
    (event) => publish(resolve(event.clientX, event.clientY)),
    { capture: true, passive: true },
  );
  publish("default");
})();
""".replace("__BINDING__", BINDING_NAME)


class CursorEventBridge:
    """Mirror the active page's CSS cursor onto the application event bus.

    A page-side observer resolves the cursor under the pointer and reports it
    through a CDP binding, so a message crosses the wire only when the cursor
    actually changes instead of once per pointer move.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._task: asyncio.Task[None] | None = None
        self._target_id: str | None = None
        self._cursor = CursorStyle.DEFAULT

    async def start(self, session: CDPSession, target_id: str) -> None:
        await self.stop()
        self._target_id = target_id
        self._cursor = CursorStyle.DEFAULT
        await session.runtime.enable()
        await session.runtime.add_binding(
            name=BINDING_NAME, execution_context_name=ISOLATED_WORLD
        )
        await session.page.add_script_to_evaluate_on_new_document(
            source=_OBSERVER_SOURCE,
            world_name=ISOLATED_WORLD,
            run_immediately=True,
        )
        self._task = asyncio.create_task(self._pump(session), name="active-page:cursor")

    async def stop(self) -> None:
        task = self._task
        self._task = None
        self._target_id = None
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _pump(self, session: CDPSession) -> None:
        try:
            async for event in session.listen(
                RuntimeEvent.BINDING_CALLED, BindingCalledEvent
            ):
                if event.name == BINDING_NAME:
                    await self._dispatch(CursorStyle.parse(event.payload))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("CDP cursor observer stopped unexpectedly")

    async def _dispatch(self, cursor: CursorStyle) -> None:
        target_id = self._target_id
        if target_id is None or cursor == self._cursor:
            return
        self._cursor = cursor
        await self._event_bus.dispatch(CursorChanged(target_id, cursor))

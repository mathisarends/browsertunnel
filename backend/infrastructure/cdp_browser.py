import asyncio
import json
import logging
from collections.abc import AsyncIterator

from cdpify import CDPSession, Client
from cdpify.domains.browser.types import PermissionDescriptor

from backend.application import (
    Browser,
    BrowserEvent,
    BrowserTab,
    BrowserTabNotFoundError,
    KeyEventType,
    MouseEventType,
    ScreencastFrame,
    TabsChanged,
    TargetDetached,
)
from backend.infrastructure.chrome_process import ChromeProcess
from backend.infrastructure.cursor_event_bridge import CursorEventBridge
from backend.infrastructure.events import BrowserEventForwarder, EventBus
from backend.infrastructure.listener_event_bridge import ListenerEventBridge
from backend.infrastructure.screencast_event_bridge import ScreencastEventBridge
from backend.settings import BrowserSettings

logger = logging.getLogger(__name__)

_CONTROL_MODIFIER = 2
_VIRTUAL_KEY_V = 86

_CDP_MOUSE_EVENT = {
    MouseEventType.DOWN: "mousePressed",
    MouseEventType.MOVE: "mouseMoved",
    MouseEventType.UP: "mouseReleased",
}

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


class CdpBrowser(Browser):
    def __init__(self, settings: BrowserSettings) -> None:
        self._settings = settings
        self._client: Client | None = None
        self._chrome_process = ChromeProcess(settings)
        self._active_target_id: str | None = None
        self._active_session: CDPSession | None = None
        self._event_bus = EventBus()
        self._event_bridge = ListenerEventBridge(self._event_bus)
        self._browser_event_forwarder = BrowserEventForwarder(self._event_bus)
        self._screencast_bridge = ScreencastEventBridge(
            self._event_bus,
            quality=settings.screencast_quality,
            width=settings.width,
            height=settings.height,
        )
        self._cursor_bridge = CursorEventBridge(self._event_bus)
        self._state_lock = asyncio.Lock()
        self._event_bus.on(TargetDetached, self._recover_active_target)

    async def start(self) -> None:
        try:
            cdp_url = self._settings.cdp_url
            if cdp_url is None:
                cdp_url = await self._chrome_process.start()
            self._client = Client(cdp_url)
            await self._client.connect()
            await self._event_bridge.start(self._client)
            await self._client.target.set_discover_targets(discover=True)
            for permission in ("clipboard-read", "clipboard-write"):
                await self._client.browser.set_permission(
                    permission=PermissionDescriptor(name=permission),
                    setting="granted",
                )
            pages = await self._page_targets()
            if not pages:
                created = await self._client.target.create_target(url="about:blank")
                target_id = created.target_id
            else:
                target_id = pages[0].target_id
            await self._select_target(target_id)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        await self._stop_active_listeners()
        await self._event_bridge.stop()
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
        await self._chrome_process.stop()

    async def events(self) -> AsyncIterator[BrowserEvent]:
        queue = self._browser_event_forwarder.subscribe()
        try:
            queue.put_nowait(TabsChanged(await self.list_tabs()))
            navigation = await self._event_bridge.current_navigation()
            if navigation is not None:
                queue.put_nowait(navigation)
            while True:
                yield await queue.get()
        finally:
            self._browser_event_forwarder.unsubscribe(queue)

    async def screencast_frames(self) -> AsyncIterator[ScreencastFrame]:
        queue = self._screencast_bridge.subscribe()
        try:
            while True:
                yield await queue.get()
        finally:
            self._screencast_bridge.unsubscribe(queue)

    async def navigate(self, url: str) -> None:
        await self._session().page.navigate(url=url)

    async def go_back(self) -> None:
        await self._navigate_history(-1)

    async def go_forward(self) -> None:
        await self._navigate_history(1)

    async def reload(self, *, ignore_cache: bool = False) -> None:
        await self._session().page.reload(ignore_cache=ignore_cache)

    async def stop_loading(self) -> None:
        await self._session().page.stop_loading()

    async def mouse(
        self,
        *,
        event_type: MouseEventType,
        x: float,
        y: float,
        button: str,
        buttons: int,
        modifiers: int,
        click_count: int,
    ) -> None:
        await self._session().input.dispatch_mouse_event(
            type=_CDP_MOUSE_EVENT[event_type],
            x=x,
            y=y,
            button=button,
            buttons=buttons,
            modifiers=modifiers,
            click_count=click_count,
        )

    async def scroll(
        self, *, x: float, y: float, delta_x: float, delta_y: float
    ) -> None:
        await self._session().input.dispatch_mouse_event(
            type="mouseWheel",
            x=x,
            y=y,
            delta_x=delta_x,
            delta_y=delta_y,
        )

    async def key(
        self,
        *,
        event_type: KeyEventType,
        key: str,
        code: str,
        text: str | None,
        unmodified_text: str | None,
        modifiers: int,
        auto_repeat: bool,
        windows_virtual_key_code: int,
        native_virtual_key_code: int,
        location: int,
        is_keypad: bool,
        is_system_key: bool,
    ) -> None:
        await self._session().input.dispatch_key_event(
            type=event_type,
            key=key,
            code=code,
            text=text,
            unmodified_text=unmodified_text,
            modifiers=modifiers,
            auto_repeat=auto_repeat,
            windows_virtual_key_code=windows_virtual_key_code,
            native_virtual_key_code=native_virtual_key_code,
            location=location,
            is_keypad=is_keypad,
            is_system_key=is_system_key,
        )

    async def insert_text(self, text: str) -> None:
        await self._session().input.insert_text(text=text)

    async def copy(self) -> str:
        """Run the page's own copy command and hand the copied text back.

        The shortcut is dispatched as an ordinary raw key event. The page clipboard
        is authoritative afterwards, but reading it can be denied, so the raw
        selection serves as a fallback.
        """
        session = self._session()
        for event_type in ("rawKeyDown", "keyUp"):
            await session.input.dispatch_key_event(
                type=event_type,
                key="c",
                code="KeyC",
                modifiers=_CONTROL_MODIFIER,
                windows_virtual_key_code=67,
                native_virtual_key_code=67,
            )
        try:
            copied = await self.read_clipboard()
        except RuntimeError:
            logger.debug("Clipboard read was denied; falling back to the selection")
            copied = ""
        return copied or await self._selection_text()

    async def _selection_text(self) -> str:
        result = await self._session().runtime.evaluate(
            expression=f"({_SELECTION_SOURCE})()",
            return_by_value=True,
        )
        if result.exception_details is not None:
            return ""
        return str(result.result.value or "")

    async def read_clipboard(self) -> str:
        result = await self._session().runtime.evaluate(
            expression="navigator.clipboard.readText()",
            await_promise=True,
            return_by_value=True,
            user_gesture=True,
        )
        if result.exception_details is not None:
            raise RuntimeError("The page denied clipboard read access")
        return str(result.result.value or "")

    async def write_clipboard(self, text: str) -> None:
        session = self._session()
        result = await session.runtime.evaluate(
            expression=f"({_COPY_SOURCE})({json.dumps(text)})",
            return_by_value=True,
            user_gesture=True,
        )
        if result.exception_details is not None or not result.result.value:
            raise ClipboardUnavailableError("The page denied clipboard write access")

    async def paste(self, text: str) -> None:
        """Put text on the page clipboard and let the page paste it natively.

        Pasting through the natural Ctrl+V chord keeps the page's own paste handling
        intact, which plain text insertion would bypass.
        """
        session = self._session()
        try:
            await self.write_clipboard(text)
        except ClipboardUnavailableError:
            logger.debug("Clipboard is unavailable; inserting pasted text directly")
            await self.insert_text(text)
            return
        for event_type in ("rawKeyDown", "keyUp"):
            await session.input.dispatch_key_event(
                type=event_type,
                key="v",
                code="KeyV",
                modifiers=_CONTROL_MODIFIER,
                windows_virtual_key_code=_VIRTUAL_KEY_V,
                native_virtual_key_code=_VIRTUAL_KEY_V,
            )

    async def list_tabs(self) -> list[BrowserTab]:
        return [
            BrowserTab(
                id=target.target_id,
                title=target.title,
                url=target.url,
                active=target.target_id == self._active_target_id,
            )
            for target in await self._page_targets()
        ]

    async def create_tab(self, url: str) -> list[BrowserTab]:
        created = await self._browser().target.create_target(url=url)
        await self._select_target(created.target_id)
        return await self.list_tabs()

    async def activate_tab(self, tab_id: str) -> list[BrowserTab]:
        await self._select_target(tab_id)
        return await self.list_tabs()

    async def close_tab(self, tab_id: str) -> list[BrowserTab]:
        client = self._browser()
        pages = await self._page_targets()
        if not any(page.target_id == tab_id for page in pages):
            raise BrowserTabNotFoundError(tab_id)
        await client.target.close_target(target_id=tab_id)
        if tab_id == self._active_target_id:
            remaining = [
                page for page in await self._page_targets() if page.target_id != tab_id
            ]
            if remaining:
                await self._select_target(remaining[0].target_id)
            else:
                created = await client.target.create_target(url="about:blank")
                await self._select_target(created.target_id)
        return await self.list_tabs()

    async def _select_target(self, target_id: str) -> None:
        client = self._browser()
        pages = await self._page_targets()
        if not any(page.target_id == target_id for page in pages):
            raise BrowserTabNotFoundError(target_id)
        async with self._state_lock:
            await self._stop_active_listeners()
            await client.target.activate_target(target_id=target_id)
            attached = await client.target.attach_to_target(
                target_id=target_id, flatten=True
            )
            self._active_target_id = target_id
            self._active_session = client.session(attached.session_id)
            await self._active_session.page.enable()
            await self._active_session.network.enable()
            await self._apply_viewport(self._active_session)
            await self._event_bridge.set_active_page(self._active_session, target_id)
            await self._cursor_bridge.start(self._active_session, target_id)
            await self._screencast_bridge.start(self._active_session)

    async def _apply_viewport(self, session: CDPSession) -> None:
        """Pin the page viewport so screencast frames match the configured size.

        Chromium's --window-size covers the whole window, so the visible page is
        smaller than requested and frames arrive with a different aspect ratio.
        """
        await session.emulation.set_device_metrics_override(
            width=self._settings.width,
            height=self._settings.height,
            device_scale_factor=1,
            mobile=False,
        )

    async def _stop_active_listeners(self) -> None:
        await self._event_bridge.clear_active_page()
        await self._cursor_bridge.stop()
        await self._screencast_bridge.stop()

    async def _navigate_history(self, offset: int) -> None:
        history = await self._session().page.get_navigation_history()
        target_index = history.current_index + offset
        if 0 <= target_index < len(history.entries):
            await self._session().page.navigate_to_history_entry(
                entry_id=history.entries[target_index].id
            )

    async def _recover_active_target(self, event: TargetDetached) -> None:
        if event.tab_id != self._active_target_id:
            return
        await asyncio.sleep(0)
        if event.tab_id != self._active_target_id:
            return
        remaining = await self._page_targets()
        if remaining:
            await self._select_target(remaining[0].target_id)
        else:
            created = await self._browser().target.create_target(url="about:blank")
            await self._select_target(created.target_id)

    async def _page_targets(self):
        targets = await self._browser().target.get_targets()
        return [target for target in targets.target_infos if target.type == "page"]

    def _browser(self) -> Client:
        if self._client is None:
            raise RuntimeError("Browser tunnel has not been started")
        return self._client

    def _session(self) -> CDPSession:
        if self._active_session is None:
            raise RuntimeError("No browser tab is active")
        return self._active_session

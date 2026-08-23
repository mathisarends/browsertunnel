import asyncio
import json
from collections.abc import AsyncIterator

from cdpify import CDPSession, Client
from cdpify.domains.browser.types import PermissionDescriptor

from backend.application import (
    Browser,
    BrowserEvent,
    BrowserTab,
    BrowserTabNotFoundError,
    ClickEventType,
    KeyEventType,
    ScreencastFrame,
    TabsChanged,
    TargetDetached,
)
from backend.infrastructure.chrome_process import ChromeProcess
from backend.infrastructure.events import BrowserEventForwarder, EventBus
from backend.infrastructure.listener_event_bridge import ListenerEventBridge
from backend.infrastructure.screencast_event_bridge import ScreencastEventBridge
from backend.settings import BrowserSettings


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

    async def click(
        self,
        *,
        event_type: ClickEventType,
        x: float,
        y: float,
        button: str,
        buttons: int,
        modifiers: int,
        click_count: int,
    ) -> None:
        await self._session().input.dispatch_mouse_event(
            type=event_type,
            x=x,
            y=y,
            button=button,
            buttons=buttons,
            modifiers=modifiers,
            click_count=click_count,
        )

    async def hover(
        self,
        *,
        x: float,
        y: float,
        buttons: int,
        modifiers: int,
    ) -> None:
        await self._session().input.dispatch_mouse_event(
            type="mouseMoved",
            x=x,
            y=y,
            button="none",
            buttons=buttons,
            modifiers=modifiers,
            click_count=0,
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
        modifiers: int,
        auto_repeat: bool,
    ) -> None:
        await self._session().input.dispatch_key_event(
            type=event_type,
            key=key,
            code=code,
            text=text,
            modifiers=modifiers,
            auto_repeat=auto_repeat,
        )

    async def insert_text(self, text: str) -> None:
        await self._session().input.insert_text(text=text)

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
        expression = f"navigator.clipboard.writeText({json.dumps(text)})"
        result = await self._session().runtime.evaluate(
            expression=expression,
            await_promise=True,
            return_by_value=True,
            user_gesture=True,
        )
        if result.exception_details is not None:
            raise RuntimeError("The page denied clipboard write access")

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

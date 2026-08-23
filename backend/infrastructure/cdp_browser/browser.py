import asyncio
import logging
from collections.abc import AsyncIterator

from cdpify import CDPSession, Client
from cdpify.domains.browser.types import PermissionDescriptor

from backend.application import (
    Browser,
    BrowserEvent,
    BrowserTabNotFoundError,
    ScreencastFrame,
    TabsChanged,
    TargetDetached,
)
from backend.infrastructure.cdp_browser.active_target import ActiveTarget
from backend.infrastructure.cdp_browser.clipboard import CdpClipboard
from backend.infrastructure.cdp_browser.input import CdpInput
from backend.infrastructure.cdp_browser.navigation import CdpNavigation
from backend.infrastructure.cdp_browser.tabs import CdpTabs, select_any_page
from backend.infrastructure.chrome_process import ChromeProcess
from backend.infrastructure.cursor_event_bridge import CursorEventBridge
from backend.infrastructure.events import BrowserEventForwarder, EventBus
from backend.infrastructure.listener_event_bridge import ListenerEventBridge
from backend.infrastructure.screencast_event_bridge import ScreencastEventBridge
from backend.settings import BrowserSettings

logger = logging.getLogger(__name__)


class CdpBrowser(Browser):
    """Drive a Chromium instance over CDP, one mirrored tab at a time."""

    def __init__(self, settings: BrowserSettings) -> None:
        self._settings = settings
        self._chrome_process = ChromeProcess(settings)
        self._target = ActiveTarget()
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
        self._clipboard = CdpClipboard(self._target)
        self._navigation = CdpNavigation(self._target)
        self._input = CdpInput(self._target, self._clipboard)
        self._tabs = CdpTabs(self._target, self._select_target)
        self._state_lock = asyncio.Lock()
        self._event_bus.on(TargetDetached, self._recover_active_target)

    @property
    def navigation(self) -> CdpNavigation:
        return self._navigation

    @property
    def input(self) -> CdpInput:
        return self._input

    @property
    def clipboard(self) -> CdpClipboard:
        return self._clipboard

    @property
    def tabs(self) -> CdpTabs:
        return self._tabs

    async def start(self) -> None:
        try:
            cdp_url = self._settings.cdp_url
            if cdp_url is None:
                cdp_url = await self._chrome_process.start()
            client = Client(cdp_url)
            self._target.attach(client)
            await client.connect()
            await self._event_bridge.start(client)
            await client.target.set_discover_targets(discover=True)
            for permission in ("clipboard-read", "clipboard-write"):
                await client.browser.set_permission(
                    permission=PermissionDescriptor(name=permission),
                    setting="granted",
                )
            await select_any_page(self._target, self._select_target)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
        await self._stop_active_listeners()
        await self._event_bridge.stop()
        client = self._target.detach()
        if client is not None:
            await client.disconnect()
        await self._chrome_process.stop()

    async def events(self) -> AsyncIterator[BrowserEvent]:
        queue = self._browser_event_forwarder.subscribe()
        try:
            queue.put_nowait(TabsChanged(await self._tabs.list()))
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

    async def _select_target(self, target_id: str) -> None:
        client = self._target.client()
        pages = await self._target.page_targets()
        if not any(page.target_id == target_id for page in pages):
            raise BrowserTabNotFoundError(target_id)
        async with self._state_lock:
            await self._stop_active_listeners()
            await client.target.activate_target(target_id=target_id)
            attached = await client.target.attach_to_target(
                target_id=target_id, flatten=True
            )
            session = client.session(attached.session_id)
            self._target.mirror(session, target_id)
            await session.page.enable()
            await session.network.enable()
            await self._apply_viewport(session)
            await self._event_bridge.set_active_page(session, target_id)
            await self._cursor_bridge.start(session, target_id)
            await self._screencast_bridge.start(session)

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

    async def _recover_active_target(self, event: TargetDetached) -> None:
        if event.tab_id != self._target.target_id:
            return
        await asyncio.sleep(0)
        if event.tab_id != self._target.target_id:
            return
        await select_any_page(self._target, self._select_target, exclude=event.tab_id)

import asyncio
import logging

from cdpify import CDPSession, Client
from cdpify.domains.network.events import LoadingFailedEvent, NetworkEvent
from cdpify.domains.page.events import (
    FrameNavigatedEvent,
    FrameStartedLoadingEvent,
    FrameStoppedLoadingEvent,
    NavigatedWithinDocumentEvent,
    PageEvent,
)
from cdpify.domains.target.events import (
    DetachedFromTargetEvent,
    TargetCrashedEvent,
    TargetCreatedEvent,
    TargetDestroyedEvent,
    TargetEvent,
    TargetInfoChangedEvent,
)
from cdpify.exceptions import CDPCommandException

from backend.application import (
    BrowserEvent,
    BrowserTab,
    NavigationChanged,
    TabsChanged,
    TargetCrashed,
    TargetDetached,
)
from backend.infrastructure.event_bus import EventBus

logger = logging.getLogger(__name__)


class ListenerEventBridge:
    """Translate CDP listener events into application-owned browser events."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._client: Client | None = None
        self._session: CDPSession | None = None
        self._active_target_id: str | None = None
        self._main_frame_id: str | None = None
        self._loading = False
        self._can_go_back = False
        self._can_go_forward = False
        self._target_tasks: set[asyncio.Task[None]] = set()
        self._page_tasks: set[asyncio.Task[None]] = set()

    async def start(self, client: Client) -> None:
        """Start every browser-level CDP listener owned by the bridge."""
        if self._target_tasks:
            return
        self._client = client
        self._target_tasks = {
            self._task(self._listen_target_created(client), TargetEvent.TARGET_CREATED),
            self._task(
                self._listen_target_destroyed(client), TargetEvent.TARGET_DESTROYED
            ),
            self._task(
                self._listen_target_info_changed(client),
                TargetEvent.TARGET_INFO_CHANGED,
            ),
            self._task(self._listen_target_crashed(client), TargetEvent.TARGET_CRASHED),
            self._task(
                self._listen_target_detached(client),
                TargetEvent.DETACHED_FROM_TARGET,
            ),
        }
        await asyncio.sleep(0)

    async def set_active_page(self, session: CDPSession, target_id: str) -> None:
        """Replace all page-level listeners with listeners for one active page."""
        await self._stop_tasks(self._page_tasks)
        self._session = session
        self._active_target_id = target_id
        self._loading = False
        self._can_go_back = False
        self._can_go_forward = False
        frame_tree = await session.page.get_frame_tree()
        self._main_frame_id = frame_tree.frame_tree.frame.id
        self._page_tasks = {
            self._task(
                self._listen_frame_navigated(session), PageEvent.FRAME_NAVIGATED
            ),
            self._task(
                self._listen_navigated_within_document(session),
                PageEvent.NAVIGATED_WITHIN_DOCUMENT,
            ),
            self._task(
                self._listen_frame_started_loading(session),
                PageEvent.FRAME_STARTED_LOADING,
            ),
            self._task(
                self._listen_frame_stopped_loading(session),
                PageEvent.FRAME_STOPPED_LOADING,
            ),
            self._task(
                self._listen_loading_failed(session), NetworkEvent.LOADING_FAILED
            ),
        }
        await asyncio.sleep(0)

    async def stop(self) -> None:
        """Stop every listener owned by the bridge."""
        await self.clear_active_page()
        await self._stop_tasks(self._target_tasks)
        self._client = None

    async def clear_active_page(self) -> None:
        await self._stop_tasks(self._page_tasks)
        self._session = None
        self._active_target_id = None
        self._main_frame_id = None

    async def current_navigation(self) -> NavigationChanged | None:
        return await self._navigation_event()

    async def _listen_target_created(self, client: Client) -> None:
        async for event in client.listen(
            TargetEvent.TARGET_CREATED, TargetCreatedEvent
        ):
            if event.target_info.type == "page":
                await self._dispatch(TabsChanged(await self._tabs()))

    async def _listen_target_destroyed(self, client: Client) -> None:
        async for event in client.listen(
            TargetEvent.TARGET_DESTROYED, TargetDestroyedEvent
        ):
            await self._dispatch(TargetDetached(event.target_id))
            await self._dispatch(TabsChanged(await self._tabs()))

    async def _listen_target_info_changed(self, client: Client) -> None:
        async for event in client.listen(
            TargetEvent.TARGET_INFO_CHANGED, TargetInfoChangedEvent
        ):
            if event.target_info.type != "page":
                continue
            await self._dispatch(TabsChanged(await self._tabs()))
            if event.target_info.target_id == self._active_target_id:
                await self._dispatch_navigation()

    async def _listen_target_crashed(self, client: Client) -> None:
        async for event in client.listen(
            TargetEvent.TARGET_CRASHED, TargetCrashedEvent
        ):
            await self._dispatch(
                TargetCrashed(event.target_id, event.status, event.error_code)
            )

    async def _listen_target_detached(self, client: Client) -> None:
        async for event in client.listen(
            TargetEvent.DETACHED_FROM_TARGET, DetachedFromTargetEvent
        ):
            await self._dispatch(TargetDetached(event.target_id))

    async def _listen_frame_navigated(self, session: CDPSession) -> None:
        async for event in session.listen(
            PageEvent.FRAME_NAVIGATED, FrameNavigatedEvent
        ):
            if event.frame.parent_id is None:
                self._main_frame_id = event.frame.id
                await self._dispatch_navigation()

    async def _listen_navigated_within_document(self, session: CDPSession) -> None:
        async for event in session.listen(
            PageEvent.NAVIGATED_WITHIN_DOCUMENT,
            NavigatedWithinDocumentEvent,
        ):
            if event.frame_id == self._main_frame_id:
                await self._dispatch_navigation()

    async def _listen_frame_started_loading(self, session: CDPSession) -> None:
        async for event in session.listen(
            PageEvent.FRAME_STARTED_LOADING, FrameStartedLoadingEvent
        ):
            if event.frame_id == self._main_frame_id:
                self._loading = True
                await self._dispatch_navigation()

    async def _listen_frame_stopped_loading(self, session: CDPSession) -> None:
        async for event in session.listen(
            PageEvent.FRAME_STOPPED_LOADING, FrameStoppedLoadingEvent
        ):
            if event.frame_id == self._main_frame_id:
                self._loading = False
                await self._dispatch_navigation()

    async def _listen_loading_failed(self, session: CDPSession) -> None:
        async for event in session.listen(
            NetworkEvent.LOADING_FAILED, LoadingFailedEvent
        ):
            if event.type == "Document" and not event.canceled:
                self._loading = False
                await self._dispatch_navigation(error=event.error_text)

    async def _dispatch_navigation(self, *, error: str | None = None) -> None:
        event = await self._navigation_event(error=error)
        if event is not None:
            await self._dispatch(event)

    async def _navigation_event(
        self, *, error: str | None = None
    ) -> NavigationChanged | None:
        target_id = self._active_target_id
        session = self._session
        if target_id is None or session is None:
            return None
        tab = next((tab for tab in await self._tabs() if tab.id == target_id), None)
        if tab is None:
            return None
        try:
            history = await session.page.get_navigation_history()
        except CDPCommandException:
            logger.debug(
                "Navigation history is temporarily unavailable for %s", target_id
            )
        else:
            self._can_go_back = history.current_index > 0
            self._can_go_forward = history.current_index < len(history.entries) - 1
        return NavigationChanged(
            tab_id=target_id,
            title=tab.title,
            url=tab.url,
            loading=self._loading,
            can_go_back=self._can_go_back,
            can_go_forward=self._can_go_forward,
            error=error,
        )

    async def _tabs(self) -> list[BrowserTab]:
        client = self._browser()
        targets = await client.target.get_targets()
        return [
            BrowserTab(
                id=target.target_id,
                title=target.title,
                url=target.url,
                active=target.target_id == self._active_target_id,
            )
            for target in targets.target_infos
            if target.type == "page"
        ]

    async def _dispatch(self, event: BrowserEvent) -> None:
        await self._event_bus.dispatch(event)

    def _browser(self) -> Client:
        if self._client is None:
            raise RuntimeError("Listener event bridge has not been started")
        return self._client

    @staticmethod
    def _task(coroutine, event_name: str) -> asyncio.Task[None]:
        return asyncio.create_task(
            coroutine,
            name=f"browser-events:{event_name}",
        )

    @staticmethod
    async def _stop_tasks(tasks: set[asyncio.Task[None]]) -> None:
        pending = tuple(tasks)
        tasks.clear()
        for task in pending:
            if not task.done():
                task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

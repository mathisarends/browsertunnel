import asyncio
import base64
from collections.abc import AsyncIterator
from typing import assert_never

from browsertunnel.features.browser.domain import (
    Browser,
    CursorChanged,
    NavigationChanged,
    ScreencastFrame,
    TabsChanged,
    TargetCrashed,
    TargetDetached,
)
from browsertunnel.features.browser.domain import (
    BrowserEvent as DomainEvent,
)
from browsertunnel.features.browser.presentation.rpc.models import (
    BrowserCursorEvent,
    BrowserEvent,
    BrowserFrameEvent,
    BrowserNavigationEvent,
    BrowserTabsEvent,
    BrowserTargetCrashedEvent,
    BrowserTargetDetachedEvent,
    tabs_result,
)

BROWSER_EVENT_METHOD = "browser.event"


def browser_event(event: DomainEvent) -> BrowserEvent:
    """Translate a domain browser event into its wire representation."""
    match event:
        case TabsChanged(tabs=tabs):
            return BrowserTabsEvent(tabs=tabs_result(tabs).tabs)
        case NavigationChanged():
            return BrowserNavigationEvent(
                tabId=event.tab_id,
                title=event.title,
                url=event.url,
                loading=event.loading,
                canGoBack=event.can_go_back,
                canGoForward=event.can_go_forward,
                error=event.error,
            )
        case CursorChanged():
            return BrowserCursorEvent(tabId=event.tab_id, cursor=event.cursor)
        case TargetCrashed():
            return BrowserTargetCrashedEvent(
                tabId=event.tab_id,
                status=event.status,
                errorCode=event.error_code,
            )
        case TargetDetached():
            return BrowserTargetDetachedEvent(tabId=event.tab_id)
        case _:
            assert_never(event)


def frame_event(frame: ScreencastFrame) -> BrowserFrameEvent:
    """Translate a screencast frame into its wire representation."""
    return BrowserFrameEvent(data=base64.b64encode(frame.data).decode("ascii"))


async def stream_browser_events(browser: Browser) -> AsyncIterator[BrowserEvent]:
    """Merge state and frames; bound buffering and stop both producers on disconnect."""
    queue: asyncio.Queue[BrowserEvent] = asyncio.Queue(maxsize=2)

    async def states() -> None:
        async for event in browser.events():
            await queue.put(browser_event(event))

    async def frames() -> None:
        async for frame in browser.screencast_frames():
            await queue.put(frame_event(frame))

    tasks = [asyncio.create_task(states()), asyncio.create_task(frames())]
    try:
        while True:
            get_event = asyncio.create_task(queue.get())
            try:
                done, _ = await asyncio.wait(
                    [get_event, *tasks], return_when=asyncio.FIRST_COMPLETED
                )
                for task in tasks:
                    if task in done:
                        task.result()
                        return
                yield get_event.result()
            finally:
                get_event.cancel()
                await asyncio.gather(get_event, return_exceptions=True)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

from collections.abc import AsyncIterator

from fastapi_rpckit import Inject, RpcLimits, RpcService

from browsertunnel.features.browser.domain import Browser

from . import methods
from .channel import channel
from .events import (
    BROWSER_EVENT_METHOD,
    browser_event,
    frame_event,
    stream_browser_events,
)
from .models import (
    BrowserCursorEvent,
    BrowserEvent,
    BrowserFrameEvent,
    BrowserNavigationEvent,
    BrowserTabsEvent,
    BrowserTargetCrashedEvent,
    BrowserTargetDetachedEvent,
    tabs_result,
)


@channel.event(BROWSER_EVENT_METHOD, payload=BrowserEvent)
async def events(browser: Inject[Browser]) -> AsyncIterator[BrowserEvent]:
    async for event in stream_browser_events(browser):
        yield event


service = RpcService(version=2)
service.socket(
    "/api/browser/ws",
    name="browser",
    channels=(channel,),
    limits=RpcLimits(max_concurrency=1),
)
BROWSER_PROTOCOL = service.protocol
contract = service.contract(title="BrowserTunnel", base_url="ws://127.0.0.1:8000")

__all__ = [
    "BROWSER_EVENT_METHOD",
    "BROWSER_PROTOCOL",
    "BrowserCursorEvent",
    "BrowserEvent",
    "BrowserFrameEvent",
    "BrowserNavigationEvent",
    "BrowserTabsEvent",
    "BrowserTargetCrashedEvent",
    "BrowserTargetDetachedEvent",
    "browser_event",
    "channel",
    "contract",
    "frame_event",
    "methods",
    "service",
    "tabs_result",
]

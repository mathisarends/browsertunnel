import base64
from typing import assert_never

from backend.application import (
    BrowserEvent as DomainEvent,
)
from backend.application import (
    CursorChanged,
    NavigationChanged,
    ScreencastFrame,
    TabsChanged,
    TargetCrashed,
    TargetDetached,
)
from backend.presentation.rpc.models import (
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

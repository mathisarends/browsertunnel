import pyrpckit as rpc

from backend.presentation.rpc.methods import BrowserRpcMethods
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

BROWSER_PROTOCOL = rpc.RpcProtocol(
    rpc.feature(
        "browser",
        handlers=(BrowserRpcMethods,),
        notifications=(
            rpc.notification(
                "browser.event",
                BrowserEvent,
                summary="Stream browser frames and tab state to the frontend.",
            ),
        ),
    ),
    version=1,
)

__all__ = [
    "BROWSER_PROTOCOL",
    "BrowserCursorEvent",
    "BrowserFrameEvent",
    "BrowserNavigationEvent",
    "BrowserRpcMethods",
    "BrowserTabsEvent",
    "BrowserTargetCrashedEvent",
    "BrowserTargetDetachedEvent",
    "tabs_result",
]

import pyrpckit as rpc

from backend.presentation.rpc.methods import BROWSER_RPC_METHODS, browser_rpc_methods
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
        handlers=BROWSER_RPC_METHODS,
        notifications=(
            rpc.notification(
                "browser.event",
                BrowserEvent,
                summary="Stream browser frames and tab state to the frontend.",
            ),
        ),
    ),
    version=2,
)

__all__ = [
    "BROWSER_PROTOCOL",
    "BrowserCursorEvent",
    "BrowserFrameEvent",
    "BrowserNavigationEvent",
    "browser_rpc_methods",
    "BrowserTabsEvent",
    "BrowserTargetCrashedEvent",
    "BrowserTargetDetachedEvent",
    "tabs_result",
]

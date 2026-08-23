from backend.application.browser import (
    BrowserEvent,
    BrowserTab,
    BrowserTabNotFoundError,
    BrowserTunnel,
    ClickEventType,
    FrameReceived,
    KeyEventType,
    NavigationChanged,
    TabsChanged,
    TargetCrashed,
    TargetDetached,
)

__all__ = [
    "BrowserEvent",
    "BrowserTab",
    "BrowserTabNotFoundError",
    "BrowserTunnel",
    "ClickEventType",
    "FrameReceived",
    "KeyEventType",
    "NavigationChanged",
    "TabsChanged",
    "TargetCrashed",
    "TargetDetached",
]

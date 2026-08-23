from backend.application.browser import (
    BrowserEvent,
    BrowserTab,
    BrowserTabNotFoundError,
    BrowserTunnel,
    FrameReceived,
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
    "FrameReceived",
    "NavigationChanged",
    "TabsChanged",
    "TargetCrashed",
    "TargetDetached",
]

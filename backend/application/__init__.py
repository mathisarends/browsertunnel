from backend.application.browser import (
    Browser,
    BrowserEvent,
    BrowserTab,
    BrowserTabNotFoundError,
    ClickEventType,
    KeyEventType,
    NavigationChanged,
    ScreencastFrame,
    TabsChanged,
    TargetCrashed,
    TargetDetached,
)

__all__ = [
    "BrowserEvent",
    "BrowserTab",
    "BrowserTabNotFoundError",
    "Browser",
    "ClickEventType",
    "KeyEventType",
    "NavigationChanged",
    "ScreencastFrame",
    "TabsChanged",
    "TargetCrashed",
    "TargetDetached",
]

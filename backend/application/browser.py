from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum


class ClickEventType(StrEnum):
    PRESSED = "mousePressed"
    RELEASED = "mouseReleased"


class KeyEventType(StrEnum):
    DOWN = "keyDown"
    UP = "keyUp"
    RAW_DOWN = "rawKeyDown"
    CHAR = "char"


class CursorStyle(StrEnum):
    """The CSS cursor keywords a page may ask the viewer to display."""

    DEFAULT = "default"
    NONE = "none"
    CONTEXT_MENU = "context-menu"
    HELP = "help"
    POINTER = "pointer"
    PROGRESS = "progress"
    WAIT = "wait"
    CELL = "cell"
    CROSSHAIR = "crosshair"
    TEXT = "text"
    VERTICAL_TEXT = "vertical-text"
    ALIAS = "alias"
    COPY = "copy"
    MOVE = "move"
    NO_DROP = "no-drop"
    NOT_ALLOWED = "not-allowed"
    GRAB = "grab"
    GRABBING = "grabbing"
    ALL_SCROLL = "all-scroll"
    COL_RESIZE = "col-resize"
    ROW_RESIZE = "row-resize"
    N_RESIZE = "n-resize"
    E_RESIZE = "e-resize"
    S_RESIZE = "s-resize"
    W_RESIZE = "w-resize"
    NE_RESIZE = "ne-resize"
    NW_RESIZE = "nw-resize"
    SE_RESIZE = "se-resize"
    SW_RESIZE = "sw-resize"
    EW_RESIZE = "ew-resize"
    NS_RESIZE = "ns-resize"
    NESW_RESIZE = "nesw-resize"
    NWSE_RESIZE = "nwse-resize"
    ZOOM_IN = "zoom-in"
    ZOOM_OUT = "zoom-out"

    @classmethod
    def parse(cls, value: str) -> CursorStyle:
        """Map an untrusted page-reported cursor onto a known keyword."""
        try:
            return cls(value.strip().lower())
        except ValueError:
            return cls.DEFAULT


@dataclass(frozen=True, slots=True)
class BrowserTab:
    id: str
    title: str
    url: str
    active: bool


@dataclass(frozen=True, slots=True)
class ScreencastFrame:
    data: bytes


@dataclass(frozen=True, slots=True)
class TabsChanged:
    tabs: list[BrowserTab]


@dataclass(frozen=True, slots=True)
class NavigationChanged:
    tab_id: str
    title: str
    url: str
    loading: bool
    can_go_back: bool
    can_go_forward: bool
    error: str | None = None


@dataclass(frozen=True, slots=True)
class TargetCrashed:
    tab_id: str
    status: str
    error_code: int


@dataclass(frozen=True, slots=True)
class TargetDetached:
    tab_id: str | None


@dataclass(frozen=True, slots=True)
class CursorChanged:
    tab_id: str
    cursor: CursorStyle


type BrowserEvent = (
    TabsChanged | NavigationChanged | TargetCrashed | TargetDetached | CursorChanged
)


class BrowserTabNotFoundError(LookupError):
    pass


class Browser(ABC):
    """Application-owned port for a controllable, screencast-capable browser."""

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def events(self) -> AsyncIterator[BrowserEvent]: ...

    @abstractmethod
    async def screencast_frames(self) -> AsyncIterator[ScreencastFrame]: ...

    @abstractmethod
    async def navigate(self, url: str) -> None: ...

    @abstractmethod
    async def go_back(self) -> None: ...

    @abstractmethod
    async def go_forward(self) -> None: ...

    @abstractmethod
    async def reload(self, *, ignore_cache: bool = False) -> None: ...

    @abstractmethod
    async def stop_loading(self) -> None: ...

    @abstractmethod
    async def click(
        self,
        *,
        event_type: ClickEventType,
        x: float,
        y: float,
        button: str,
        buttons: int,
        modifiers: int,
        click_count: int,
    ) -> None: ...

    @abstractmethod
    async def hover(
        self,
        *,
        x: float,
        y: float,
        buttons: int,
        modifiers: int,
    ) -> None: ...

    @abstractmethod
    async def scroll(
        self, *, x: float, y: float, delta_x: float, delta_y: float
    ) -> None: ...

    @abstractmethod
    async def key(
        self,
        *,
        event_type: KeyEventType,
        key: str,
        code: str,
        text: str | None,
        modifiers: int,
        auto_repeat: bool,
    ) -> None: ...

    @abstractmethod
    async def insert_text(self, text: str) -> None: ...

    @abstractmethod
    async def paste(self, text: str) -> None: ...

    @abstractmethod
    async def read_clipboard(self) -> str: ...

    @abstractmethod
    async def write_clipboard(self, text: str) -> None: ...

    @abstractmethod
    async def list_tabs(self) -> list[BrowserTab]: ...

    @abstractmethod
    async def create_tab(self, url: str) -> list[BrowserTab]: ...

    @abstractmethod
    async def activate_tab(self, tab_id: str) -> list[BrowserTab]: ...

    @abstractmethod
    async def close_tab(self, tab_id: str) -> list[BrowserTab]: ...

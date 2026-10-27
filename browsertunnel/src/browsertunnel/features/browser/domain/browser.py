from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum


class MouseEventType(StrEnum):
    DOWN = "mouseDown"
    MOVE = "mouseMove"
    UP = "mouseUp"


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


class BrowserNavigation(ABC):
    """Move the mirrored tab through the web."""

    @abstractmethod
    async def navigate(self, url: str) -> None: ...

    @abstractmethod
    async def back(self) -> None: ...

    @abstractmethod
    async def forward(self) -> None: ...

    @abstractmethod
    async def reload(self, *, ignore_cache: bool = False) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...


class BrowserInput(ABC):
    """Replay viewer input on the mirrored tab."""

    @abstractmethod
    async def mouse(
        self,
        *,
        event_type: MouseEventType,
        x: float,
        y: float,
        button: str,
        buttons: int,
        modifiers: int,
        click_count: int,
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
        unmodified_text: str | None,
        modifiers: int,
        auto_repeat: bool,
        windows_virtual_key_code: int,
        native_virtual_key_code: int,
        location: int,
        is_keypad: bool,
        is_system_key: bool,
    ) -> None: ...

    @abstractmethod
    async def insert_text(self, text: str) -> None: ...

    @abstractmethod
    async def paste(self, text: str) -> None: ...


class BrowserClipboard(ABC):
    """Exchange text between the viewer and the mirrored tab."""

    @abstractmethod
    async def copy(self) -> str: ...

    @abstractmethod
    async def read(self) -> str: ...

    @abstractmethod
    async def write(self, text: str) -> None: ...


class BrowserTabs(ABC):
    """Inspect and switch the tabs the tunnel can mirror.

    Every command answers with the full tab list, so a viewer never has to
    re-query to learn which tab the tunnel ended up on.
    """

    @abstractmethod
    async def list(self) -> list[BrowserTab]: ...

    @abstractmethod
    async def create(self, url: str) -> list[BrowserTab]: ...

    @abstractmethod
    async def activate(self, tab_id: str) -> list[BrowserTab]: ...

    @abstractmethod
    async def close(self, tab_id: str) -> list[BrowserTab]: ...


class Browser(ABC):
    """Application-owned port for a controllable, screencast-capable browser.

    Commands are grouped by what they act on, so a caller depends on the one
    namespace it drives instead of on every command the tunnel offers.
    """

    @property
    @abstractmethod
    def navigation(self) -> BrowserNavigation: ...

    @property
    @abstractmethod
    def input(self) -> BrowserInput: ...

    @property
    @abstractmethod
    def clipboard(self) -> BrowserClipboard: ...

    @property
    @abstractmethod
    def tabs(self) -> BrowserTabs: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def events(self) -> AsyncIterator[BrowserEvent]: ...

    @abstractmethod
    def screencast_frames(self) -> AsyncIterator[ScreencastFrame]: ...

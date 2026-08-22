from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal

type MouseEventType = Literal[
    "mousePressed", "mouseReleased", "mouseMoved", "mouseWheel"
]
type KeyEventType = Literal["keyDown", "keyUp", "rawKeyDown", "char"]


@dataclass(frozen=True, slots=True)
class BrowserTab:
    id: str
    title: str
    url: str
    active: bool


@dataclass(frozen=True, slots=True)
class BrowserFrame:
    data: str
    session_id: int
    metadata: dict[str, Any]


class BrowserTunnel(ABC):
    """Application-owned port for one remotely controlled browser."""

    @abstractmethod
    async def frames(self) -> AsyncIterator[BrowserFrame]: ...

    @abstractmethod
    async def navigate(self, url: str) -> None: ...

    @abstractmethod
    async def mouse(
        self,
        *,
        event_type: MouseEventType,
        x: float,
        y: float,
        button: str | None,
        buttons: int | None,
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
        modifiers: int,
        auto_repeat: bool,
    ) -> None: ...

    @abstractmethod
    async def insert_text(self, text: str) -> None: ...

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

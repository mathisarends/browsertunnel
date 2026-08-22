from enum import StrEnum
from typing import Any, Literal

import pyrpckit as rpc
from pydantic import BaseModel, ConfigDict, Field

from backend.application import BrowserTab, BrowserTunnel
from backend.infrastructure.cdp_browser import BrowserTargetNotFoundError


class RpcModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class BrowserRpcMethod(StrEnum):
    NAVIGATE = "browser.navigate"
    MOUSE = "browser.mouse"
    SCROLL = "browser.scroll"
    KEY = "browser.key"
    INSERT_TEXT = "browser.text.insert"
    READ_CLIPBOARD = "browser.clipboard.read"
    WRITE_CLIPBOARD = "browser.clipboard.write"
    LIST_TABS = "browser.tab.list"
    CREATE_TAB = "browser.tab.create"
    ACTIVATE_TAB = "browser.tab.activate"
    CLOSE_TAB = "browser.tab.close"


class EmptyParams(RpcModel):
    pass


class EmptyResult(RpcModel):
    pass


class NavigateParams(RpcModel):
    url: str = Field(min_length=1)


class MouseParams(RpcModel):
    type: Literal["mousePressed", "mouseReleased", "mouseMoved"]
    x: float
    y: float
    button: Literal["none", "left", "middle", "right", "back", "forward"] | None = None
    buttons: int | None = Field(default=None, ge=0)
    modifiers: int = Field(default=0, ge=0)
    click_count: int = Field(default=1, alias="clickCount", ge=0)


class ScrollParams(RpcModel):
    x: float
    y: float
    delta_x: float = Field(alias="deltaX")
    delta_y: float = Field(alias="deltaY")


class KeyParams(RpcModel):
    type: Literal["keyDown", "keyUp", "rawKeyDown", "char"]
    key: str
    code: str = ""
    text: str | None = None
    modifiers: int = Field(default=0, ge=0)
    auto_repeat: bool = Field(default=False, alias="autoRepeat")


class TextParams(RpcModel):
    text: str


class TabParams(RpcModel):
    tab_id: str = Field(alias="tabId", min_length=1)


class CreateTabParams(RpcModel):
    url: str = "about:blank"


class TabResult(RpcModel):
    id: str
    title: str
    url: str
    active: bool


class TabsResult(RpcModel):
    tabs: list[TabResult]


class ClipboardResult(RpcModel):
    text: str


class BrowserTabNotFound(rpc.RpcError):
    code = -32004
    message = "Browser tab not found"


@rpc.event
class BrowserFrameEvent(RpcModel):
    type: Literal["browser.frame"] = "browser.frame"
    data: str
    session_id: int = Field(alias="sessionId")
    metadata: dict[str, Any]


@rpc.event
class BrowserTabsEvent(RpcModel):
    type: Literal["browser.tabs"] = "browser.tabs"
    tabs: list[TabResult]


type BrowserEvent = BrowserFrameEvent | BrowserTabsEvent


def tabs_result(tabs: list[BrowserTab]) -> TabsResult:
    return TabsResult(tabs=[TabResult(**vars_from_tab(tab)) for tab in tabs])


def vars_from_tab(tab: BrowserTab) -> dict[str, str | bool]:
    return {"id": tab.id, "title": tab.title, "url": tab.url, "active": tab.active}


class BrowserRpcMethods(rpc.RpcHandler):
    def __init__(self, browser: BrowserTunnel) -> None:
        self._browser = browser

    @rpc.method(BrowserRpcMethod.NAVIGATE)
    async def navigate(self, params: NavigateParams) -> EmptyResult:
        """Navigate the active tab to a URL."""
        await self._browser.navigate(params.url)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.MOUSE)
    async def mouse(self, params: MouseParams) -> EmptyResult:
        """Dispatch a mouse event to the active tab."""
        await self._browser.mouse(
            event_type=params.type,
            x=params.x,
            y=params.y,
            button=params.button,
            buttons=params.buttons,
            modifiers=params.modifiers,
            click_count=params.click_count,
        )
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.SCROLL)
    async def scroll(self, params: ScrollParams) -> EmptyResult:
        """Scroll the active tab at the given canvas coordinates."""
        await self._browser.scroll(
            x=params.x,
            y=params.y,
            delta_x=params.delta_x,
            delta_y=params.delta_y,
        )
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.KEY)
    async def key(self, params: KeyParams) -> EmptyResult:
        """Dispatch a keyboard event to the active tab."""
        await self._browser.key(
            event_type=params.type,
            key=params.key,
            code=params.code,
            text=params.text,
            modifiers=params.modifiers,
            auto_repeat=params.auto_repeat,
        )
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.INSERT_TEXT)
    async def insert_text(self, params: TextParams) -> EmptyResult:
        """Insert text, including IME and emoji input, into the active tab."""
        await self._browser.insert_text(params.text)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.READ_CLIPBOARD)
    async def read_clipboard(self, params: EmptyParams) -> ClipboardResult:
        """Read text from the active page clipboard."""
        return ClipboardResult(text=await self._browser.read_clipboard())

    @rpc.method(BrowserRpcMethod.WRITE_CLIPBOARD)
    async def write_clipboard(self, params: TextParams) -> EmptyResult:
        """Write text to the active page clipboard."""
        await self._browser.write_clipboard(params.text)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.LIST_TABS)
    async def list_tabs(self, params: EmptyParams) -> TabsResult:
        """List all browser tabs and identify the active one."""
        return tabs_result(await self._browser.list_tabs())

    @rpc.method(BrowserRpcMethod.CREATE_TAB)
    async def create_tab(self, params: CreateTabParams) -> TabsResult:
        """Create and activate a browser tab."""
        return tabs_result(await self._browser.create_tab(params.url))

    @rpc.method(BrowserRpcMethod.ACTIVATE_TAB, errors=(BrowserTabNotFound,))
    async def activate_tab(self, params: TabParams) -> TabsResult:
        """Activate an existing browser tab."""
        try:
            tabs = await self._browser.activate_tab(params.tab_id)
        except BrowserTargetNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

    @rpc.method(BrowserRpcMethod.CLOSE_TAB, errors=(BrowserTabNotFound,))
    async def close_tab(self, params: TabParams) -> TabsResult:
        """Close a browser tab and activate a remaining tab."""
        try:
            tabs = await self._browser.close_tab(params.tab_id)
        except BrowserTargetNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)


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

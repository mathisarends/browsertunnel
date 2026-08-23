from enum import StrEnum
from typing import Literal

import pyrpckit as rpc
from pydantic import BaseModel, ConfigDict, Field

from backend.application import (
    BrowserTab,
    BrowserTabNotFoundError,
    BrowserTunnel,
    ClickEventType,
    KeyEventType,
)


class RpcModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class BrowserRpcMethod(StrEnum):
    NAVIGATE = "browser.navigate"
    GO_BACK = "browser.goBack"
    GO_FORWARD = "browser.goForward"
    RELOAD = "browser.reload"
    STOP_LOADING = "browser.stopLoading"
    CLICK = "browser.click"
    HOVER = "browser.hover"
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


class ReloadParams(RpcModel):
    ignore_cache: bool = Field(default=False, alias="ignoreCache")


class ClickParams(RpcModel):
    type: ClickEventType
    x: float
    y: float
    button: Literal["left", "middle", "right", "back", "forward"]
    buttons: int = Field(ge=0)
    modifiers: int = Field(default=0, ge=0)
    click_count: int = Field(default=1, alias="clickCount", ge=0)


class HoverParams(RpcModel):
    x: float
    y: float
    buttons: int = Field(default=0, ge=0)
    modifiers: int = Field(default=0, ge=0)


class ScrollParams(RpcModel):
    x: float
    y: float
    delta_x: float = Field(alias="deltaX")
    delta_y: float = Field(alias="deltaY")


class KeyParams(RpcModel):
    type: KeyEventType
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


@rpc.event
class BrowserTabsEvent(RpcModel):
    type: Literal["browser.tabs"] = "browser.tabs"
    tabs: list[TabResult]


@rpc.event
class BrowserNavigationEvent(RpcModel):
    type: Literal["browser.navigation"] = "browser.navigation"
    tab_id: str = Field(alias="tabId")
    title: str
    url: str
    loading: bool
    can_go_back: bool = Field(alias="canGoBack")
    can_go_forward: bool = Field(alias="canGoForward")
    error: str | None = None


@rpc.event
class BrowserTargetCrashedEvent(RpcModel):
    type: Literal["browser.targetCrashed"] = "browser.targetCrashed"
    tab_id: str = Field(alias="tabId")
    status: str
    error_code: int = Field(alias="errorCode")


@rpc.event
class BrowserTargetDetachedEvent(RpcModel):
    type: Literal["browser.targetDetached"] = "browser.targetDetached"
    tab_id: str | None = Field(alias="tabId")


type BrowserEvent = (
    BrowserFrameEvent
    | BrowserTabsEvent
    | BrowserNavigationEvent
    | BrowserTargetCrashedEvent
    | BrowserTargetDetachedEvent
)


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

    @rpc.method(BrowserRpcMethod.GO_BACK)
    async def go_back(self, params: EmptyParams) -> EmptyResult:
        """Navigate the active tab to its previous history entry, if available."""
        await self._browser.go_back()
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.GO_FORWARD)
    async def go_forward(self, params: EmptyParams) -> EmptyResult:
        """Navigate the active tab to its next history entry, if available."""
        await self._browser.go_forward()
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.RELOAD)
    async def reload(self, params: ReloadParams) -> EmptyResult:
        """Reload the active tab, optionally bypassing its cache."""
        await self._browser.reload(ignore_cache=params.ignore_cache)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.STOP_LOADING)
    async def stop_loading(self, params: EmptyParams) -> EmptyResult:
        """Stop loading the active tab."""
        await self._browser.stop_loading()
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.CLICK)
    async def click(self, params: ClickParams) -> EmptyResult:
        """Dispatch a mouse button event to the active tab."""
        await self._browser.click(
            event_type=params.type,
            x=params.x,
            y=params.y,
            button=params.button,
            buttons=params.buttons,
            modifiers=params.modifiers,
            click_count=params.click_count,
        )
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.HOVER)
    async def hover(self, params: HoverParams) -> EmptyResult:
        """Move the pointer in the active tab to update hover state."""
        await self._browser.hover(
            x=params.x,
            y=params.y,
            buttons=params.buttons,
            modifiers=params.modifiers,
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
        except BrowserTabNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

    @rpc.method(BrowserRpcMethod.CLOSE_TAB, errors=(BrowserTabNotFound,))
    async def close_tab(self, params: TabParams) -> TabsResult:
        """Close a browser tab and activate a remaining tab."""
        try:
            tabs = await self._browser.close_tab(params.tab_id)
        except BrowserTabNotFoundError as error:
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

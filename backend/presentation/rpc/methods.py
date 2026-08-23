from enum import StrEnum

import pyrpckit as rpc

from backend.application import Browser, BrowserTabNotFoundError
from backend.presentation.rpc.models import (
    ClickParams,
    ClipboardResult,
    CreateTabParams,
    EmptyParams,
    EmptyResult,
    HoverParams,
    KeyParams,
    NavigateParams,
    ReloadParams,
    ScrollParams,
    TabParams,
    TabsResult,
    TextParams,
    tabs_result,
)


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
    PASTE = "browser.clipboard.paste"
    READ_CLIPBOARD = "browser.clipboard.read"
    WRITE_CLIPBOARD = "browser.clipboard.write"
    LIST_TABS = "browser.tab.list"
    CREATE_TAB = "browser.tab.create"
    ACTIVATE_TAB = "browser.tab.activate"
    CLOSE_TAB = "browser.tab.close"


class BrowserTabNotFound(rpc.RpcError):
    code = -32004
    message = "Browser tab not found"


class BrowserRpcMethods(rpc.RpcHandler):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @rpc.method(BrowserRpcMethod.NAVIGATE)
    async def navigate(self, params: NavigateParams) -> EmptyResult:
        await self._browser.navigate(params.url)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.GO_BACK)
    async def go_back(self, params: EmptyParams) -> EmptyResult:
        await self._browser.go_back()
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.GO_FORWARD)
    async def go_forward(self, params: EmptyParams) -> EmptyResult:
        await self._browser.go_forward()
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.RELOAD)
    async def reload(self, params: ReloadParams) -> EmptyResult:
        await self._browser.reload(ignore_cache=params.ignore_cache)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.STOP_LOADING)
    async def stop_loading(self, params: EmptyParams) -> EmptyResult:
        await self._browser.stop_loading()
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.CLICK)
    async def click(self, params: ClickParams) -> EmptyResult:
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
        await self._browser.hover(
            x=params.x,
            y=params.y,
            buttons=params.buttons,
            modifiers=params.modifiers,
        )
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.SCROLL)
    async def scroll(self, params: ScrollParams) -> EmptyResult:
        await self._browser.scroll(
            x=params.x,
            y=params.y,
            delta_x=params.delta_x,
            delta_y=params.delta_y,
        )
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.KEY)
    async def key(self, params: KeyParams) -> EmptyResult:
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
        await self._browser.insert_text(params.text)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.PASTE)
    async def paste(self, params: TextParams) -> EmptyResult:
        await self._browser.paste(params.text)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.READ_CLIPBOARD)
    async def read_clipboard(self, params: EmptyParams) -> ClipboardResult:
        return ClipboardResult(text=await self._browser.read_clipboard())

    @rpc.method(BrowserRpcMethod.WRITE_CLIPBOARD)
    async def write_clipboard(self, params: TextParams) -> EmptyResult:
        await self._browser.write_clipboard(params.text)
        return EmptyResult()

    @rpc.method(BrowserRpcMethod.LIST_TABS)
    async def list_tabs(self, params: EmptyParams) -> TabsResult:
        return tabs_result(await self._browser.list_tabs())

    @rpc.method(BrowserRpcMethod.CREATE_TAB)
    async def create_tab(self, params: CreateTabParams) -> TabsResult:
        return tabs_result(await self._browser.create_tab(params.url))

    @rpc.method(BrowserRpcMethod.ACTIVATE_TAB, errors=(BrowserTabNotFound,))
    async def activate_tab(self, params: TabParams) -> TabsResult:
        try:
            tabs = await self._browser.activate_tab(params.tab_id)
        except BrowserTabNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

    @rpc.method(BrowserRpcMethod.CLOSE_TAB, errors=(BrowserTabNotFound,))
    async def close_tab(self, params: TabParams) -> TabsResult:
        try:
            tabs = await self._browser.close_tab(params.tab_id)
        except BrowserTabNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

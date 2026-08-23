from enum import StrEnum

import pyrpckit as rpc

from backend.application import Browser, BrowserTabNotFoundError
from backend.presentation.rpc.models import (
    CreateTabParams,
    EmptyParams,
    TabParams,
    TabsResult,
    tabs_result,
)


class TabMethod(StrEnum):
    LIST = "browser.tab.list"
    CREATE = "browser.tab.create"
    ACTIVATE = "browser.tab.activate"
    CLOSE = "browser.tab.close"


class BrowserTabNotFound(rpc.RpcError):
    code = -32004
    message = "Browser tab not found"


class TabMethods(rpc.RpcHandler):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @rpc.method(TabMethod.LIST)
    async def list(self, params: EmptyParams) -> TabsResult:
        return tabs_result(await self._browser.list_tabs())

    @rpc.method(TabMethod.CREATE)
    async def create(self, params: CreateTabParams) -> TabsResult:
        return tabs_result(await self._browser.create_tab(params.url))

    @rpc.method(TabMethod.ACTIVATE, errors=(BrowserTabNotFound,))
    async def activate(self, params: TabParams) -> TabsResult:
        try:
            tabs = await self._browser.activate_tab(params.tab_id)
        except BrowserTabNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

    @rpc.method(TabMethod.CLOSE, errors=(BrowserTabNotFound,))
    async def close(self, params: TabParams) -> TabsResult:
        try:
            tabs = await self._browser.close_tab(params.tab_id)
        except BrowserTabNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

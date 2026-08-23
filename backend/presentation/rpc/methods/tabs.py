from enum import StrEnum

import pyrpckit as rpc

from backend.application import BrowserTabNotFoundError, BrowserTabs
from backend.presentation.rpc.models import (
    CreateTabParams,
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
    def __init__(self, tabs: BrowserTabs) -> None:
        self._tabs = tabs

    @rpc.method(TabMethod.LIST)
    async def list(self) -> TabsResult:
        return tabs_result(await self._tabs.list())

    @rpc.method(TabMethod.CREATE)
    async def create(self, params: CreateTabParams) -> TabsResult:
        return tabs_result(await self._tabs.create(params.url))

    @rpc.method(TabMethod.ACTIVATE, errors=(BrowserTabNotFound,))
    async def activate(self, params: TabParams) -> TabsResult:
        try:
            tabs = await self._tabs.activate(params.tab_id)
        except BrowserTabNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

    @rpc.method(TabMethod.CLOSE, errors=(BrowserTabNotFound,))
    async def close(self, params: TabParams) -> TabsResult:
        try:
            tabs = await self._tabs.close(params.tab_id)
        except BrowserTabNotFoundError as error:
            raise BrowserTabNotFound(
                f"Browser tab not found: {params.tab_id}"
            ) from error
        return tabs_result(tabs)

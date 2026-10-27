from enum import StrEnum

from fastapi_rpckit import Inject, RpcError

from browsertunnel.features.browser.domain import (
    Browser,
    BrowserTabNotFoundError,
)
from browsertunnel.features.browser.presentation.rpc.channel import channel
from browsertunnel.features.browser.presentation.rpc.models import (
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


class BrowserTabNotFound(RpcError):
    code = "browser_tab_not_found"
    rpc_code = -32004
    message = "Browser tab not found"


@channel.method(TabMethod.LIST, idempotent=True)
async def list(browser: Inject[Browser]) -> TabsResult:
    return tabs_result(await browser.tabs.list())


@channel.method(TabMethod.CREATE)
async def create(params: CreateTabParams, browser: Inject[Browser]) -> TabsResult:
    return tabs_result(await browser.tabs.create(params.url))


@channel.method(TabMethod.ACTIVATE, raises=(BrowserTabNotFound,))
async def activate(params: TabParams, browser: Inject[Browser]) -> TabsResult:
    try:
        tabs = await browser.tabs.activate(params.tab_id)
    except BrowserTabNotFoundError as error:
        raise BrowserTabNotFound(
            message=f"Browser tab not found: {params.tab_id}"
        ) from error
    return tabs_result(tabs)


@channel.method(TabMethod.CLOSE, raises=(BrowserTabNotFound,))
async def close(params: TabParams, browser: Inject[Browser]) -> TabsResult:
    try:
        tabs = await browser.tabs.close(params.tab_id)
    except BrowserTabNotFoundError as error:
        raise BrowserTabNotFound(
            message=f"Browser tab not found: {params.tab_id}"
        ) from error
    return tabs_result(tabs)

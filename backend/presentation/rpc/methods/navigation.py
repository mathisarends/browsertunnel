from enum import StrEnum

import pyrpckit as rpc

from backend.application import Browser
from backend.presentation.rpc.models import (
    EmptyParams,
    NavigateParams,
    ReloadParams,
)


class NavigationMethod(StrEnum):
    NAVIGATE = "browser.nav.navigate"
    BACK = "browser.nav.back"
    FORWARD = "browser.nav.forward"
    RELOAD = "browser.nav.reload"
    STOP = "browser.nav.stop"


class NavigationMethods(rpc.RpcHandler):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @rpc.method(NavigationMethod.NAVIGATE)
    async def navigate(self, params: NavigateParams) -> None:
        await self._browser.navigate(params.url)

    @rpc.method(NavigationMethod.BACK)
    async def back(self, _params: EmptyParams) -> None:
        await self._browser.go_back()

    @rpc.method(NavigationMethod.FORWARD)
    async def forward(self, _params: EmptyParams) -> None:
        await self._browser.go_forward()

    @rpc.method(NavigationMethod.RELOAD)
    async def reload(self, params: ReloadParams) -> None:
        await self._browser.reload(ignore_cache=params.ignore_cache)

    @rpc.method(NavigationMethod.STOP)
    async def stop(self, _params: EmptyParams) -> None:
        await self._browser.stop_loading()

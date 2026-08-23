from enum import StrEnum

import pyrpckit as rpc

from backend.application import BrowserNavigation
from backend.presentation.rpc.models import (
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
    def __init__(self, navigation: BrowserNavigation) -> None:
        self._navigation = navigation

    @rpc.method(NavigationMethod.NAVIGATE)
    async def navigate(self, params: NavigateParams) -> None:
        await self._navigation.navigate(params.url)

    @rpc.method(NavigationMethod.BACK)
    async def back(self) -> None:
        await self._navigation.back()

    @rpc.method(NavigationMethod.FORWARD)
    async def forward(self) -> None:
        await self._navigation.forward()

    @rpc.method(NavigationMethod.RELOAD)
    async def reload(self, params: ReloadParams) -> None:
        await self._navigation.reload(ignore_cache=params.ignore_cache)

    @rpc.method(NavigationMethod.STOP)
    async def stop(self) -> None:
        await self._navigation.stop()

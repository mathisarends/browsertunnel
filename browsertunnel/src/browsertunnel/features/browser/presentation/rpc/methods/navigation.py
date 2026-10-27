from enum import StrEnum

from fastapi_rpckit import Inject

from browsertunnel.features.browser.domain import Browser
from browsertunnel.features.browser.presentation.rpc.channel import channel
from browsertunnel.features.browser.presentation.rpc.models import (
    NavigateParams,
    ReloadParams,
)


class NavigationMethod(StrEnum):
    NAVIGATE = "browser.nav.navigate"
    BACK = "browser.nav.back"
    FORWARD = "browser.nav.forward"
    RELOAD = "browser.nav.reload"
    STOP = "browser.nav.stop"


@channel.method(NavigationMethod.NAVIGATE)
async def navigate(params: NavigateParams, browser: Inject[Browser]) -> None:
    await browser.navigation.navigate(params.url)


@channel.method(NavigationMethod.BACK)
async def back(browser: Inject[Browser]) -> None:
    await browser.navigation.back()


@channel.method(NavigationMethod.FORWARD)
async def forward(browser: Inject[Browser]) -> None:
    await browser.navigation.forward()


@channel.method(NavigationMethod.RELOAD)
async def reload(params: ReloadParams, browser: Inject[Browser]) -> None:
    await browser.navigation.reload(ignore_cache=params.ignore_cache)


@channel.method(NavigationMethod.STOP)
async def stop(browser: Inject[Browser]) -> None:
    await browser.navigation.stop()

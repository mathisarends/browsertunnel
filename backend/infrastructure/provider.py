from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide

from backend.application import BrowserTunnel
from backend.infrastructure.cdp_browser import CdpBrowserTunnel
from backend.settings import BrowserSettings


class BrowserTunnelProvider(Provider):
    @provide(scope=Scope.APP)
    def settings(self) -> BrowserSettings:
        return BrowserSettings()

    @provide(scope=Scope.APP, provides=BrowserTunnel)
    async def browser(
        self, settings: BrowserSettings
    ) -> AsyncIterator[CdpBrowserTunnel]:
        browser = CdpBrowserTunnel(settings)
        try:
            await browser.start()
            yield browser
        finally:
            await browser.close()

from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide

from backend.application import Browser
from backend.infrastructure.cdp_browser import CdpBrowser
from backend.settings import BrowserSettings


class BrowserProvider(Provider):
    @provide(scope=Scope.APP)
    def settings(self) -> BrowserSettings:
        return BrowserSettings()

    @provide(scope=Scope.APP, provides=Browser)
    async def browser(self, settings: BrowserSettings) -> AsyncIterator[CdpBrowser]:
        browser = CdpBrowser(settings)
        try:
            await browser.start()
            yield browser
        finally:
            await browser.stop()

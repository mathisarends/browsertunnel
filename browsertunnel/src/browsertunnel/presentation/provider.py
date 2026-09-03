from dishka import Provider, Scope, provide

from browsertunnel.application import Browser
from browsertunnel.presentation.session import BrowserSessionFactory


class SessionProvider(Provider):
    @provide(scope=Scope.APP)
    def sessions(self, browser: Browser) -> BrowserSessionFactory:
        return BrowserSessionFactory(browser)

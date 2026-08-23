from dishka import Provider, Scope, provide

from backend.application import Browser
from backend.presentation.session import BrowserSessionFactory


class SessionProvider(Provider):
    @provide(scope=Scope.APP)
    def sessions(self, browser: Browser) -> BrowserSessionFactory:
        return BrowserSessionFactory(browser)

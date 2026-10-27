from fastapi import FastAPI
from fastapi_canon import Composition

from browsertunnel.features.browser.feature import browser_tunnel_feature


def create_app() -> FastAPI:
    return Composition(browser_tunnel_feature).apply(
        FastAPI(title="BrowserTunnel", version="0.1.0")
    )


app = create_app()

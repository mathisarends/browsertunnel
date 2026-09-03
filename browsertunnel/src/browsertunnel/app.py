from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from browsertunnel.infrastructure.provider import BrowserProvider
from browsertunnel.lifespan import lifespan
from browsertunnel.presentation import SessionProvider, router


def create_app() -> FastAPI:
    app = FastAPI(title="BrowserTunnel", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    setup_dishka(make_async_container(BrowserProvider(), SessionProvider()), app)
    return app


app = create_app()

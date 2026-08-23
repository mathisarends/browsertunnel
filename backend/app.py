from dishka import make_async_container
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from backend.infrastructure.provider import BrowserProvider
from backend.lifespan import lifespan
from backend.presentation import router


def create_app() -> FastAPI:
    app = FastAPI(title="BrowserTunnel", version="0.1.0", lifespan=lifespan)
    app.include_router(router)
    setup_dishka(make_async_container(BrowserProvider()), app)
    return app


app = create_app()

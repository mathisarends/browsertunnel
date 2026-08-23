import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.application import Browser

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("Starting up BrowserTunnel API")
    container = app.state.dishka_container
    await container.get(Browser)
    try:
        yield
    finally:
        logger.info("Shutting down BrowserTunnel API")
        await container.close()

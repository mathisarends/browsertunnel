from fastapi_canon import Feature
from fastapi_rpckit.integrations.dishka import dishka_router

from .infrastructure.provider import BrowserProvider
from .lifespan import lifespan
from .presentation.router import router
from .presentation.rpc import service

browser_tunnel_feature = Feature(
    name="browser-tunnel",
    routers=[router, dishka_router(service)],
    providers=[BrowserProvider],
    lifespan=lifespan,
)

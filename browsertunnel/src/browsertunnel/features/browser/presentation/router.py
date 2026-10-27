from fastapi_canon import CanonRouter

from browsertunnel.features.browser.presentation.schemas import (
    browser_json_schema,
    browser_openrpc_schema,
)

router = CanonRouter(prefix="/api/browser", tags=["browser-tunnel"])


@router.get("/schema.json", include_in_schema=False)
async def json_rpc_schema() -> dict:
    return browser_json_schema()


@router.get("/openrpc.json", include_in_schema=False)
async def open_rpc_schema() -> dict:
    return browser_openrpc_schema()

import asyncio
import base64
import json
from contextlib import suppress

import pyrpckit as rpc
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.application import (
    BrowserTunnel,
    FrameReceived,
    NavigationChanged,
    TabsChanged,
    TargetCrashed,
    TargetDetached,
)
from backend.presentation.rpc import (
    BROWSER_PROTOCOL,
    BrowserFrameEvent,
    BrowserNavigationEvent,
    BrowserRpcMethods,
    BrowserTabsEvent,
    BrowserTargetCrashedEvent,
    BrowserTargetDetachedEvent,
    tabs_result,
)
from backend.presentation.schemas import browser_json_schema, browser_openrpc_schema

router = APIRouter(prefix="/api/browser", tags=["browser-tunnel"])


@router.get("/schema.json", include_in_schema=False)
async def json_rpc_schema() -> dict:
    return browser_json_schema()


@router.get("/openrpc.json", include_in_schema=False)
async def open_rpc_schema() -> dict:
    return browser_openrpc_schema()


@router.websocket("/ws")
@inject
async def browser_socket(
    websocket: WebSocket,
    browser: FromDishka[BrowserTunnel],
) -> None:
    await websocket.accept()
    send_lock = asyncio.Lock()
    server = rpc.RpcServer(
        BrowserRpcMethods(browser),
        protocol=BROWSER_PROTOCOL,
    )

    async def send(model) -> None:
        async with send_lock:
            await websocket.send_json(model.model_dump(mode="json", by_alias=True))

    async def stream_events() -> None:
        async for event in browser.events():
            match event:
                case FrameReceived(data=data):
                    params = BrowserFrameEvent(
                        data=base64.b64encode(data).decode("ascii")
                    )
                case TabsChanged(tabs=tabs):
                    params = BrowserTabsEvent(tabs=tabs_result(tabs).tabs)
                case NavigationChanged():
                    params = BrowserNavigationEvent(
                        tabId=event.tab_id,
                        title=event.title,
                        url=event.url,
                        loading=event.loading,
                        canGoBack=event.can_go_back,
                        canGoForward=event.can_go_forward,
                        error=event.error,
                    )
                case TargetCrashed():
                    params = BrowserTargetCrashedEvent(
                        tabId=event.tab_id,
                        status=event.status,
                        errorCode=event.error_code,
                    )
                case TargetDetached():
                    params = BrowserTargetDetachedEvent(tabId=event.tab_id)
            await send(
                rpc.RpcNotification(
                    method="browser.event",
                    params=params,
                )
            )

    event_task = asyncio.create_task(stream_events())
    try:
        while True:
            raw_request = await websocket.receive_text()
            try:
                request = json.loads(raw_request)
            except json.JSONDecodeError:
                await send(server.failure(None, rpc.RpcParseError()))
                continue
            response = await server.handle(request)
            if response is not None:
                await send(response)
    except WebSocketDisconnect:
        pass
    finally:
        event_task.cancel()
        with suppress(asyncio.CancelledError):
            await event_task

import asyncio
import json
from contextlib import suppress

import pyrpckit as rpc
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pyrpckit.schema import render_json_schema, render_openrpc

from backend.application import BrowserTunnel
from backend.presentation.rpc import (
    BROWSER_PROTOCOL,
    BrowserFrameEvent,
    BrowserRpcMethods,
    BrowserTabsEvent,
    tabs_result,
)

router = APIRouter(prefix="/api/browser", tags=["browser-tunnel"])

_TAB_METHODS = {
    "browser.tab.create",
    "browser.tab.activate",
    "browser.tab.close",
}


@router.get("/schema.json", include_in_schema=False)
async def json_rpc_schema() -> dict:
    return render_json_schema(
        BROWSER_PROTOCOL,
        title="BrowserTunnel JSON-RPC Protocol",
        schema_id="/api/browser/schema.json",
    )


@router.get("/openrpc.json", include_in_schema=False)
async def open_rpc_schema() -> dict:
    return render_openrpc(
        BROWSER_PROTOCOL,
        title="BrowserTunnel",
        servers=({"name": "browser-tunnel", "url": "/api/browser/ws"},),
    )


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

    async def stream_frames() -> None:
        tabs = tabs_result(await browser.list_tabs())
        await send(
            rpc.RpcNotification(
                method="browser.event",
                params=BrowserTabsEvent(tabs=tabs.tabs),
            )
        )
        async for frame in browser.frames():
            await send(
                rpc.RpcNotification(
                    method="browser.event",
                    params=BrowserFrameEvent(
                        data=frame.data,
                        sessionId=frame.session_id,
                        metadata=frame.metadata,
                    ),
                )
            )

    frame_task = asyncio.create_task(stream_frames())
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
            if (
                isinstance(request, dict)
                and request.get("method") in _TAB_METHODS
                and isinstance(response, rpc.RpcSuccess)
            ):
                tabs = tabs_result(await browser.list_tabs())
                await send(
                    rpc.RpcNotification(
                        method="browser.event",
                        params=BrowserTabsEvent(tabs=tabs.tabs),
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        frame_task.cancel()
        with suppress(asyncio.CancelledError):
            await frame_task

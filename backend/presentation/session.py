import asyncio
import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

import pyrpckit as rpc
from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from backend.application import Browser
from backend.presentation.rpc import (
    BROWSER_EVENT_METHOD,
    BROWSER_PROTOCOL,
    BrowserEvent,
    browser_event,
    browser_rpc_methods,
    frame_event,
)


class BrowserSession:
    """Serve one viewer: RPC requests in, browser events and frames out."""

    def __init__(self, websocket: WebSocket, browser: Browser) -> None:
        self._websocket = websocket
        self._browser = browser
        self._send_lock = asyncio.Lock()
        self._server = rpc.RpcServer(
            *browser_rpc_methods(browser),
            protocol=BROWSER_PROTOCOL,
        )

    async def run(self) -> None:
        await self._websocket.accept()
        async with self._streaming():
            with suppress(WebSocketDisconnect):
                await self._serve_requests()

    async def _serve_requests(self) -> None:
        while True:
            raw_request = await self._websocket.receive_text()
            try:
                request = json.loads(raw_request)
            except json.JSONDecodeError:
                await self._send(self._server.failure(None, rpc.RpcParseError()))
                continue
            response = await self._server.handle(request)
            if response is not None:
                await self._send(response)

    @asynccontextmanager
    async def _streaming(self) -> AsyncGenerator[None]:
        tasks = (
            asyncio.create_task(self._stream_events()),
            asyncio.create_task(self._stream_screencast()),
        )
        try:
            yield
        finally:
            for task in tasks:
                task.cancel()
            with suppress(asyncio.CancelledError):
                await asyncio.gather(*tasks)

    async def _stream_events(self) -> None:
        async for event in self._browser.events():
            await self._notify(browser_event(event))

    async def _stream_screencast(self) -> None:
        async for frame in self._browser.screencast_frames():
            await self._notify(frame_event(frame))

    async def _notify(self, params: BrowserEvent) -> None:
        await self._send(
            rpc.RpcNotification(method=BROWSER_EVENT_METHOD, params=params)
        )

    async def _send(self, message: BaseModel) -> None:
        async with self._send_lock:
            await self._websocket.send_json(
                message.model_dump(mode="json", by_alias=True)
            )


class BrowserSessionFactory:
    """Bind the injected browser to the websocket of a single viewer."""

    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    def create(self, websocket: WebSocket) -> BrowserSession:
        return BrowserSession(websocket, self._browser)

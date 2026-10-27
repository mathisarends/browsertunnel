"""Exercise Canon startup, schemas and RPC against a real local Chromium."""

import asyncio
import json
from urllib.request import urlopen

import uvicorn
from websockets.asyncio.client import connect

from browsertunnel.app import create_app


async def main() -> None:
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=0, log_level="warning")
    )
    serving = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(20):
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("Server stopped during startup")
                await asyncio.sleep(0.05)
        port = server.servers[0].sockets[0].getsockname()[1]
        for endpoint in ("schema.json", "openrpc.json"):

            def read_schema(endpoint=endpoint):
                with urlopen(
                    f"http://127.0.0.1:{port}/api/browser/{endpoint}", timeout=5
                ) as response:
                    return json.load(response)

            document = await asyncio.to_thread(read_schema)
            assert document["x-rpc-protocol-version"] == 2
        async with connect(f"ws://127.0.0.1:{port}/api/browser/ws") as socket:
            events = set()
            navigation = {}

            def record(message):
                if message.get("method") == "browser.event":
                    event = message["params"]
                    events.add(event["type"])
                    if event["type"] == "browser.navigation":
                        navigation.update(event)

            async def call(request_id, method, params=None):
                request = {"jsonrpc": "2.0", "id": request_id, "method": method}
                if params is not None:
                    request["params"] = params
                await socket.send(json.dumps(request))
                async with asyncio.timeout(10):
                    while True:
                        message = json.loads(await socket.recv())
                        record(message)
                        if message.get("id") == request_id:
                            assert "error" not in message, message
                            return message["result"]

            initial = await call(1, "browser.tab.list")
            assert initial["tabs"]
            result = await call(2, "browser.tab.create", {"url": "about:blank"})
            assert len(result["tabs"]) == len(initial["tabs"]) + 1
            new_tab = next(tab["id"] for tab in result["tabs"] if tab["active"])
            await call(
                3,
                "browser.nav.navigate",
                {"url": "data:text/html,<title>Canon smoke</title><input autofocus>"},
            )
            async with asyncio.timeout(10):
                while navigation.get("title") != "Canon smoke" or navigation.get(
                    "loading", True
                ):
                    record(json.loads(await socket.recv()))
            await call(4, "browser.input.text.insert", {"text": "Canon"})
            await call(
                5,
                "browser.input.key",
                {
                    "type": "rawKeyDown",
                    "key": "a",
                    "code": "KeyA",
                    "modifiers": 2,
                    "windowsVirtualKeyCode": 65,
                },
            )
            assert (await call(6, "browser.clipboard.copy"))["text"] == "Canon"
            async with asyncio.timeout(10):
                while (
                    not {"browser.frame", "browser.navigation", "browser.tabs"}
                    <= events
                ):
                    message = json.loads(await socket.recv())
                    if message.get("method") == "browser.event":
                        events.add(message["params"]["type"])
            result = await call(7, "browser.tab.close", {"tabId": new_tab})
            assert len(result["tabs"]) == len(initial["tabs"])
            await socket.send("{")
            async with asyncio.timeout(5):
                while True:
                    message = json.loads(await socket.recv())
                    if "error" in message:
                        assert message["error"]["code"] == -32700
                        break
            print(
                "Canon app smoke passed: schemas, tabs, navigation, input, clipboard, "
                "events, parse errors and disconnect"
            )
    finally:
        server.should_exit = True
        await serving


if __name__ == "__main__":
    asyncio.run(main())

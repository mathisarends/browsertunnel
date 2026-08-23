from collections.abc import AsyncIterator

import pytest
from pyrpckit import RpcServer
from pyrpckit.schema import render_json_schema, render_openrpc

from backend.application import BrowserEvent, BrowserTab, BrowserTunnel
from backend.presentation.rpc import BROWSER_PROTOCOL, BrowserRpcMethods


class FakeBrowser(BrowserTunnel):
    def __init__(self) -> None:
        self.navigated_to: str | None = None
        self.navigation_commands: list[tuple[str, bool | None]] = []
        self.tabs = [BrowserTab("tab-1", "Example", "about:blank", True)]

    async def events(self) -> AsyncIterator[BrowserEvent]:
        if False:
            yield

    async def navigate(self, url: str) -> None:
        self.navigated_to = url

    async def go_back(self) -> None:
        self.navigation_commands.append(("back", None))

    async def go_forward(self) -> None:
        self.navigation_commands.append(("forward", None))

    async def reload(self, *, ignore_cache: bool = False) -> None:
        self.navigation_commands.append(("reload", ignore_cache))

    async def stop_loading(self) -> None:
        self.navigation_commands.append(("stop", None))

    async def mouse(self, **kwargs) -> None:
        pass

    async def scroll(self, **kwargs) -> None:
        pass

    async def key(self, **kwargs) -> None:
        pass

    async def insert_text(self, text: str) -> None:
        pass

    async def read_clipboard(self) -> str:
        return "clipboard"

    async def write_clipboard(self, text: str) -> None:
        pass

    async def list_tabs(self) -> list[BrowserTab]:
        return self.tabs

    async def create_tab(self, url: str) -> list[BrowserTab]:
        return self.tabs

    async def activate_tab(self, tab_id: str) -> list[BrowserTab]:
        return self.tabs

    async def close_tab(self, tab_id: str) -> list[BrowserTab]:
        return self.tabs


@pytest.mark.asyncio
async def test_json_rpc_dispatches_browser_commands() -> None:
    browser = FakeBrowser()
    server = RpcServer(BrowserRpcMethods(browser), protocol=BROWSER_PROTOCOL)

    response = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "browser.navigate",
            "params": {"url": "https://example.com"},
        }
    )

    assert response is not None
    assert response.model_dump(mode="json") == {
        "jsonrpc": "2.0",
        "id": 7,
        "result": {},
    }
    assert browser.navigated_to == "https://example.com"


@pytest.mark.asyncio
async def test_json_rpc_rejects_invalid_params() -> None:
    server = RpcServer(BrowserRpcMethods(FakeBrowser()), protocol=BROWSER_PROTOCOL)

    response = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": "bad",
            "method": "browser.scroll",
            "params": {"x": 1, "y": 2, "deltaX": 3},
        }
    )

    assert response is not None
    assert response.error.code == -32602


@pytest.mark.asyncio
async def test_json_rpc_dispatches_navigation_toolbar_commands() -> None:
    browser = FakeBrowser()
    server = RpcServer(BrowserRpcMethods(browser), protocol=BROWSER_PROTOCOL)

    for request_id, method, params in (
        (1, "browser.goBack", {}),
        (2, "browser.goForward", {}),
        (3, "browser.reload", {"ignoreCache": True}),
        (4, "browser.stopLoading", {}),
    ):
        response = await server.handle(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        assert response is not None
        assert response.model_dump(mode="json")["result"] == {}

    assert browser.navigation_commands == [
        ("back", None),
        ("forward", None),
        ("reload", True),
        ("stop", None),
    ]


def test_protocol_contract_contains_methods_and_events() -> None:
    schema = render_json_schema(BROWSER_PROTOCOL, title="BrowserTunnel")
    openrpc = render_openrpc(BROWSER_PROTOCOL, title="BrowserTunnel")

    assert {method["name"] for method in schema["x-rpc-methods"]} >= {
        "browser.navigate",
        "browser.goBack",
        "browser.goForward",
        "browser.reload",
        "browser.stopLoading",
        "browser.mouse",
        "browser.tab.create",
        "browser.clipboard.write",
    }
    assert {event["name"] for event in schema["x-rpc-events"]} == {
        "browser.frame",
        "browser.navigation",
        "browser.tabs",
        "browser.targetCrashed",
        "browser.targetDetached",
    }
    assert openrpc["openrpc"] == "1.3.2"

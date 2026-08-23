from collections.abc import AsyncIterator

import pytest
from pyrpckit import RpcServer
from pyrpckit.schema import render_json_schema, render_openrpc

from backend.application import BrowserEvent, BrowserTab, ScreencastFrame
from backend.presentation.rpc import BROWSER_PROTOCOL, browser_rpc_methods


class FakeNavigation:
    def __init__(self) -> None:
        self.navigated_to: str | None = None
        self.commands: list[tuple[str, bool | None]] = []

    async def navigate(self, url: str) -> None:
        self.navigated_to = url

    async def back(self) -> None:
        self.commands.append(("back", None))

    async def forward(self) -> None:
        self.commands.append(("forward", None))

    async def reload(self, *, ignore_cache: bool = False) -> None:
        self.commands.append(("reload", ignore_cache))

    async def stop(self) -> None:
        self.commands.append(("stop", None))


class FakeInput:
    def __init__(self) -> None:
        self.mouse_events: list[dict] = []
        self.key_events: list[dict] = []
        self.pasted: list[str] = []

    async def mouse(self, **kwargs) -> None:
        self.mouse_events.append(kwargs)

    async def scroll(self, **kwargs) -> None:
        pass

    async def key(self, **kwargs) -> None:
        self.key_events.append(kwargs)

    async def insert_text(self, text: str) -> None:
        pass

    async def paste(self, text: str) -> None:
        self.pasted.append(text)


class FakeClipboard:
    def __init__(self) -> None:
        self.copies = 0

    async def copy(self) -> str:
        self.copies += 1
        return "copied selection"

    async def read(self) -> str:
        return "clipboard"

    async def write(self, text: str) -> None:
        pass


class FakeTabs:
    def __init__(self) -> None:
        self.tabs = [BrowserTab("tab-1", "Example", "about:blank", True)]

    async def list(self) -> list[BrowserTab]:
        return self.tabs

    async def create(self, url: str) -> list[BrowserTab]:
        return self.tabs

    async def activate(self, tab_id: str) -> list[BrowserTab]:
        return self.tabs

    async def close(self, tab_id: str) -> list[BrowserTab]:
        return self.tabs


class FakeBrowser:
    def __init__(self) -> None:
        self.navigation = FakeNavigation()
        self.input = FakeInput()
        self.clipboard = FakeClipboard()
        self.tabs = FakeTabs()

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def events(self) -> AsyncIterator[BrowserEvent]:
        if False:
            yield

    async def screencast_frames(self) -> AsyncIterator[ScreencastFrame]:
        if False:
            yield


@pytest.mark.asyncio
async def test_json_rpc_dispatches_browser_commands() -> None:
    browser = FakeBrowser()
    server = RpcServer(*browser_rpc_methods(browser), protocol=BROWSER_PROTOCOL)

    response = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "browser.nav.navigate",
            "params": {"url": "https://example.com"},
        }
    )

    assert response is not None
    assert response.model_dump(mode="json") == {
        "jsonrpc": "2.0",
        "id": 7,
        "result": None,
    }
    assert browser.navigation.navigated_to == "https://example.com"


@pytest.mark.asyncio
async def test_json_rpc_pastes_viewer_clipboard_text() -> None:
    browser = FakeBrowser()
    server = RpcServer(*browser_rpc_methods(browser), protocol=BROWSER_PROTOCOL)

    response = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "browser.input.paste",
            "params": {"text": "from the local machine"},
        }
    )

    assert response is not None
    assert response.model_dump(mode="json")["result"] is None
    assert browser.input.pasted == ["from the local machine"]


@pytest.mark.asyncio
async def test_json_rpc_returns_the_pages_copied_selection() -> None:
    browser = FakeBrowser()
    server = RpcServer(*browser_rpc_methods(browser), protocol=BROWSER_PROTOCOL)

    response = await server.handle(
        {"jsonrpc": "2.0", "id": 11, "method": "browser.clipboard.copy"}
    )

    assert response is not None
    assert response.model_dump(mode="json")["result"] == {"text": "copied selection"}
    assert browser.clipboard.copies == 1


@pytest.mark.asyncio
async def test_json_rpc_rejects_invalid_params() -> None:
    server = RpcServer(*browser_rpc_methods(FakeBrowser()), protocol=BROWSER_PROTOCOL)

    response = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": "bad",
            "method": "browser.input.scroll",
            "params": {"x": 1, "y": 2, "deltaX": 3},
        }
    )

    assert response is not None
    assert response.error.code == -32602


@pytest.mark.asyncio
async def test_json_rpc_dispatches_navigation_toolbar_commands() -> None:
    browser = FakeBrowser()
    server = RpcServer(*browser_rpc_methods(browser), protocol=BROWSER_PROTOCOL)

    for request_id, method, params in (
        (1, "browser.nav.back", None),
        (2, "browser.nav.forward", None),
        (3, "browser.nav.reload", {"ignoreCache": True}),
        (4, "browser.nav.stop", None),
    ):
        request = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            request["params"] = params
        response = await server.handle(request)
        assert response is not None
        assert response.model_dump(mode="json")["result"] is None

    assert browser.navigation.commands == [
        ("back", None),
        ("forward", None),
        ("reload", True),
        ("stop", None),
    ]


@pytest.mark.asyncio
async def test_json_rpc_dispatches_generic_mouse_sequence() -> None:
    browser = FakeBrowser()
    server = RpcServer(*browser_rpc_methods(browser), protocol=BROWSER_PROTOCOL)

    for request_id, params in enumerate(
        (
            {
                "type": "mouseDown",
                "x": 100,
                "y": 200,
                "button": "left",
                "buttons": 1,
                "clickCount": 1,
            },
            {
                "type": "mouseMove",
                "x": 123.5,
                "y": 456.25,
                "button": "left",
                "buttons": 1,
            },
            {
                "type": "mouseUp",
                "x": 123.5,
                "y": 456.25,
                "button": "left",
                "buttons": 0,
                "clickCount": 1,
            },
        ),
        start=5,
    ):
        response = await server.handle(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "browser.input.mouse",
                "params": params,
            }
        )
        assert response is not None
        assert response.model_dump(mode="json")["result"] is None

    assert browser.input.mouse_events == [
        {
            "event_type": "mouseDown",
            "x": 100.0,
            "y": 200.0,
            "button": "left",
            "buttons": 1,
            "modifiers": 0,
            "click_count": 1,
        },
        {
            "event_type": "mouseMove",
            "x": 123.5,
            "y": 456.25,
            "button": "left",
            "buttons": 1,
            "modifiers": 0,
            "click_count": 0,
        },
        {
            "event_type": "mouseUp",
            "x": 123.5,
            "y": 456.25,
            "button": "left",
            "buttons": 0,
            "modifiers": 0,
            "click_count": 1,
        },
    ]


@pytest.mark.asyncio
async def test_json_rpc_dispatches_complete_special_key_data() -> None:
    browser = FakeBrowser()
    server = RpcServer(*browser_rpc_methods(browser), protocol=BROWSER_PROTOCOL)

    response = await server.handle(
        {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "browser.input.key",
            "params": {
                "type": "rawKeyDown",
                "key": "Delete",
                "code": "Delete",
                "windowsVirtualKeyCode": 46,
                "nativeVirtualKeyCode": 46,
                "location": 0,
                "isKeypad": False,
            },
        }
    )

    assert response is not None
    assert response.model_dump(mode="json")["result"] is None
    assert browser.input.key_events == [
        {
            "event_type": "rawKeyDown",
            "key": "Delete",
            "code": "Delete",
            "text": None,
            "unmodified_text": None,
            "modifiers": 0,
            "auto_repeat": False,
            "windows_virtual_key_code": 46,
            "native_virtual_key_code": 46,
            "location": 0,
            "is_keypad": False,
            "is_system_key": False,
        }
    ]


def test_protocol_contract_contains_methods_and_events() -> None:
    schema = render_json_schema(BROWSER_PROTOCOL, title="BrowserTunnel")
    openrpc = render_openrpc(BROWSER_PROTOCOL, title="BrowserTunnel")
    methods = {method["name"] for method in schema["x-rpc-methods"]}

    assert methods == {
        "browser.nav.navigate",
        "browser.nav.back",
        "browser.nav.forward",
        "browser.nav.reload",
        "browser.nav.stop",
        "browser.input.mouse",
        "browser.input.scroll",
        "browser.input.key",
        "browser.input.text.insert",
        "browser.input.paste",
        "browser.clipboard.copy",
        "browser.clipboard.read",
        "browser.clipboard.write",
        "browser.tab.list",
        "browser.tab.create",
        "browser.tab.activate",
        "browser.tab.close",
    }
    assert {event["name"] for event in schema["x-rpc-events"]} == {
        "browser.cursor",
        "browser.frame",
        "browser.navigation",
        "browser.tabs",
        "browser.targetCrashed",
        "browser.targetDetached",
    }
    assert openrpc["openrpc"] == "1.3.2"
    assert schema["x-rpc-protocol-version"] == 2
    assert openrpc["x-rpc-protocol-version"] == 2

    parameterless = {
        method["name"]: method
        for method in openrpc["methods"]
        if method["name"]
        in {
            "browser.nav.back",
            "browser.nav.forward",
            "browser.nav.stop",
            "browser.clipboard.copy",
            "browser.clipboard.read",
            "browser.tab.list",
        }
    }
    assert all(method["params"] == [] for method in parameterless.values())
    assert all("x-rpc-params-schema" not in method for method in parameterless.values())

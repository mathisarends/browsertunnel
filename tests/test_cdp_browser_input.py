from types import SimpleNamespace

import pytest

from backend.application import KeyEventType, MouseEventType
from backend.infrastructure.cdp_browser import CdpBrowser


class RecordingInput:
    def __init__(self) -> None:
        self.mouse_events: list[dict] = []
        self.key_events: list[dict] = []

    async def dispatch_mouse_event(self, **kwargs) -> None:
        self.mouse_events.append(kwargs)

    async def dispatch_key_event(self, **kwargs) -> None:
        self.key_events.append(kwargs)


class ClipboardRuntime:
    async def evaluate(self, **kwargs):
        return SimpleNamespace(
            exception_details=None,
            result=SimpleNamespace(value="selected text"),
        )


def browser_with_recording_session() -> tuple[CdpBrowser, RecordingInput]:
    browser = object.__new__(CdpBrowser)
    input_domain = RecordingInput()
    browser._active_session = SimpleNamespace(  # noqa: SLF001
        input=input_domain,
        runtime=ClipboardRuntime(),
    )
    return browser, input_domain


@pytest.mark.asyncio
async def test_mouse_primitives_map_directly_to_cdp_events() -> None:
    browser, input_domain = browser_with_recording_session()

    for event_type, x, y, button, buttons in (
        (MouseEventType.DOWN, 10, 20, "left", 1),
        (MouseEventType.MOVE, 10, 80, "none", 1),
        (MouseEventType.UP, 10, 80, "left", 0),
    ):
        await browser.mouse(
            event_type=event_type,
            x=x,
            y=y,
            button=button,
            buttons=buttons,
            modifiers=2,
            click_count=1,
        )

    assert [event["type"] for event in input_domain.mouse_events] == [
        "mousePressed",
        "mouseMoved",
        "mouseReleased",
    ]
    assert input_domain.mouse_events[1] == {
        "type": "mouseMoved",
        "x": 10,
        "y": 80,
        "button": "none",
        "buttons": 1,
        "modifiers": 2,
        "click_count": 1,
    }


@pytest.mark.asyncio
async def test_special_key_metadata_is_forwarded_unchanged_to_cdp() -> None:
    browser, input_domain = browser_with_recording_session()

    await browser.key(
        event_type=KeyEventType.RAW_DOWN,
        key="Backspace",
        code="Backspace",
        text=None,
        unmodified_text=None,
        modifiers=2,
        auto_repeat=False,
        windows_virtual_key_code=8,
        native_virtual_key_code=8,
        location=0,
        is_keypad=False,
        is_system_key=False,
    )

    assert input_domain.key_events == [
        {
            "type": "rawKeyDown",
            "key": "Backspace",
            "code": "Backspace",
            "text": None,
            "unmodified_text": None,
            "modifiers": 2,
            "auto_repeat": False,
            "windows_virtual_key_code": 8,
            "native_virtual_key_code": 8,
            "location": 0,
            "is_keypad": False,
            "is_system_key": False,
        }
    ]


@pytest.mark.asyncio
async def test_copy_uses_natural_ctrl_c_without_editing_commands() -> None:
    browser, input_domain = browser_with_recording_session()

    assert await browser.copy() == "selected text"

    assert [event["type"] for event in input_domain.key_events] == [
        "rawKeyDown",
        "keyUp",
    ]
    assert all(event["key"] == "c" for event in input_domain.key_events)
    assert all(event["modifiers"] == 2 for event in input_domain.key_events)
    assert all("commands" not in event for event in input_domain.key_events)

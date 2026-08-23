from types import SimpleNamespace

import pytest

from backend.application import KeyEventType, MouseEventType
from backend.infrastructure.cdp_browser import CdpClipboard, CdpInput
from backend.infrastructure.cdp_browser.active_target import ActiveTarget


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


def recording_target() -> tuple[ActiveTarget, RecordingInput]:
    input_domain = RecordingInput()
    target = ActiveTarget()
    session = SimpleNamespace(input=input_domain, runtime=ClipboardRuntime())
    target.mirror(session, "tab-1")
    return target, input_domain


@pytest.mark.asyncio
async def test_mouse_primitives_preserve_the_held_button_during_a_drag() -> None:
    target, input_domain = recording_target()
    browser_input = CdpInput(target, CdpClipboard(target))

    for event_type, x, y, button, buttons in (
        (MouseEventType.DOWN, 10, 20, "left", 1),
        (MouseEventType.MOVE, 10, 80, "left", 1),
        (MouseEventType.UP, 10, 80, "left", 0),
    ):
        await browser_input.mouse(
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
        "button": "left",
        "buttons": 1,
        "modifiers": 2,
        "click_count": 1,
    }


@pytest.mark.asyncio
async def test_special_key_metadata_is_forwarded_unchanged_to_cdp() -> None:
    target, input_domain = recording_target()
    browser_input = CdpInput(target, CdpClipboard(target))

    await browser_input.key(
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
    target, input_domain = recording_target()

    assert await CdpClipboard(target).copy() == "selected text"

    assert [event["type"] for event in input_domain.key_events] == [
        "rawKeyDown",
        "keyUp",
    ]
    assert all(event["key"] == "c" for event in input_domain.key_events)
    assert all(event["modifiers"] == 2 for event in input_domain.key_events)
    assert all("commands" not in event for event in input_domain.key_events)

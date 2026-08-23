import logging

from backend.application import BrowserInput, KeyEventType, MouseEventType
from backend.infrastructure.cdp_browser.active_target import ActiveTarget
from backend.infrastructure.cdp_browser.clipboard import (
    CdpClipboard,
    ClipboardUnavailableError,
)

logger = logging.getLogger(__name__)

_CONTROL_MODIFIER = 2
_VIRTUAL_KEY_V = 86

_CDP_MOUSE_EVENT = {
    MouseEventType.DOWN: "mousePressed",
    MouseEventType.MOVE: "mouseMoved",
    MouseEventType.UP: "mouseReleased",
}


class CdpInput(BrowserInput):
    def __init__(self, target: ActiveTarget, clipboard: CdpClipboard) -> None:
        self._target = target
        self._clipboard = clipboard

    async def mouse(
        self,
        *,
        event_type: MouseEventType,
        x: float,
        y: float,
        button: str,
        buttons: int,
        modifiers: int,
        click_count: int,
    ) -> None:
        await self._target.session().input.dispatch_mouse_event(
            type=_CDP_MOUSE_EVENT[event_type],
            x=x,
            y=y,
            button=button,
            buttons=buttons,
            modifiers=modifiers,
            click_count=click_count,
        )

    async def scroll(
        self, *, x: float, y: float, delta_x: float, delta_y: float
    ) -> None:
        await self._target.session().input.dispatch_mouse_event(
            type="mouseWheel",
            x=x,
            y=y,
            delta_x=delta_x,
            delta_y=delta_y,
        )

    async def key(
        self,
        *,
        event_type: KeyEventType,
        key: str,
        code: str,
        text: str | None,
        unmodified_text: str | None,
        modifiers: int,
        auto_repeat: bool,
        windows_virtual_key_code: int,
        native_virtual_key_code: int,
        location: int,
        is_keypad: bool,
        is_system_key: bool,
    ) -> None:
        await self._target.session().input.dispatch_key_event(
            type=event_type,
            key=key,
            code=code,
            text=text,
            unmodified_text=unmodified_text,
            modifiers=modifiers,
            auto_repeat=auto_repeat,
            windows_virtual_key_code=windows_virtual_key_code,
            native_virtual_key_code=native_virtual_key_code,
            location=location,
            is_keypad=is_keypad,
            is_system_key=is_system_key,
        )

    async def insert_text(self, text: str) -> None:
        await self._target.session().input.insert_text(text=text)

    async def paste(self, text: str) -> None:
        """Put text on the page clipboard and let the page paste it natively.

        Pasting through the natural Ctrl+V chord keeps the page's own paste handling
        intact, which plain text insertion would bypass.
        """
        session = self._target.session()
        try:
            await self._clipboard.write(text)
        except ClipboardUnavailableError:
            logger.debug("Clipboard is unavailable; inserting pasted text directly")
            await self.insert_text(text)
            return
        for event_type in ("rawKeyDown", "keyUp"):
            await session.input.dispatch_key_event(
                type=event_type,
                key="v",
                code="KeyV",
                modifiers=_CONTROL_MODIFIER,
                windows_virtual_key_code=_VIRTUAL_KEY_V,
                native_virtual_key_code=_VIRTUAL_KEY_V,
            )

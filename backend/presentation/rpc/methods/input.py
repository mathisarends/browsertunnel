from enum import StrEnum

import pyrpckit as rpc

from backend.application import Browser
from backend.presentation.rpc.models import (
    KeyParams,
    MouseParams,
    ScrollParams,
    TextParams,
)


class InputMethod(StrEnum):
    MOUSE = "browser.input.mouse"
    SCROLL = "browser.input.scroll"
    KEY = "browser.input.key"
    INSERT_TEXT = "browser.input.text.insert"
    PASTE = "browser.input.paste"


class InputMethods(rpc.RpcHandler):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @rpc.method(InputMethod.MOUSE)
    async def mouse(self, params: MouseParams) -> None:
        await self._browser.mouse(
            event_type=params.type,
            x=params.x,
            y=params.y,
            button=params.button,
            buttons=params.buttons,
            modifiers=params.modifiers,
            click_count=params.click_count,
        )

    @rpc.method(InputMethod.SCROLL)
    async def scroll(self, params: ScrollParams) -> None:
        await self._browser.scroll(
            x=params.x,
            y=params.y,
            delta_x=params.delta_x,
            delta_y=params.delta_y,
        )

    @rpc.method(InputMethod.KEY)
    async def key(self, params: KeyParams) -> None:
        await self._browser.key(
            event_type=params.type,
            key=params.key,
            code=params.code,
            text=params.text,
            unmodified_text=params.unmodified_text,
            modifiers=params.modifiers,
            auto_repeat=params.auto_repeat,
            windows_virtual_key_code=params.windows_virtual_key_code,
            native_virtual_key_code=params.native_virtual_key_code,
            location=params.location,
            is_keypad=params.is_keypad,
            is_system_key=params.is_system_key,
        )

    @rpc.method(InputMethod.INSERT_TEXT)
    async def insert_text(self, params: TextParams) -> None:
        await self._browser.insert_text(params.text)

    @rpc.method(InputMethod.PASTE)
    async def paste(self, params: TextParams) -> None:
        await self._browser.paste(params.text)

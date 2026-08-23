from enum import StrEnum

import pyrpckit as rpc

from backend.application import Browser
from backend.presentation.rpc.models import (
    ClickParams,
    HoverParams,
    KeyParams,
    ScrollParams,
    TextParams,
)


class InputMethod(StrEnum):
    CLICK = "browser.input.click"
    HOVER = "browser.input.hover"
    SCROLL = "browser.input.scroll"
    KEY = "browser.input.key"
    INSERT_TEXT = "browser.input.text.insert"
    PASTE = "browser.input.paste"


class InputMethods(rpc.RpcHandler):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @rpc.method(InputMethod.CLICK)
    async def click(self, params: ClickParams) -> None:
        await self._browser.click(
            event_type=params.type,
            x=params.x,
            y=params.y,
            button=params.button,
            buttons=params.buttons,
            modifiers=params.modifiers,
            click_count=params.click_count,
        )

    @rpc.method(InputMethod.HOVER)
    async def hover(self, params: HoverParams) -> None:
        await self._browser.hover(
            x=params.x,
            y=params.y,
            buttons=params.buttons,
            modifiers=params.modifiers,
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
            modifiers=params.modifiers,
            auto_repeat=params.auto_repeat,
        )

    @rpc.method(InputMethod.INSERT_TEXT)
    async def insert_text(self, params: TextParams) -> None:
        await self._browser.insert_text(params.text)

    @rpc.method(InputMethod.PASTE)
    async def paste(self, params: TextParams) -> None:
        await self._browser.paste(params.text)

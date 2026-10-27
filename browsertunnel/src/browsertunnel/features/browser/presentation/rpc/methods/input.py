from enum import StrEnum

from fastapi_rpckit import Inject

from browsertunnel.features.browser.domain import Browser
from browsertunnel.features.browser.presentation.rpc.channel import channel
from browsertunnel.features.browser.presentation.rpc.models import (
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


@channel.method(InputMethod.MOUSE)
async def mouse(params: MouseParams, browser: Inject[Browser]) -> None:
    await browser.input.mouse(
        event_type=params.type,
        x=params.x,
        y=params.y,
        button=params.button,
        buttons=params.buttons,
        modifiers=params.modifiers,
        click_count=params.click_count,
    )


@channel.method(InputMethod.SCROLL)
async def scroll(params: ScrollParams, browser: Inject[Browser]) -> None:
    await browser.input.scroll(
        x=params.x,
        y=params.y,
        delta_x=params.delta_x,
        delta_y=params.delta_y,
    )


@channel.method(InputMethod.KEY)
async def key(params: KeyParams, browser: Inject[Browser]) -> None:
    await browser.input.key(
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


@channel.method(InputMethod.INSERT_TEXT)
async def insert_text(params: TextParams, browser: Inject[Browser]) -> None:
    await browser.input.insert_text(params.text)


@channel.method(InputMethod.PASTE)
async def paste(params: TextParams, browser: Inject[Browser]) -> None:
    await browser.input.paste(params.text)

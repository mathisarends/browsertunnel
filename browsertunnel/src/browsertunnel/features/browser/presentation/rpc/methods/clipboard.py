from enum import StrEnum

from fastapi_rpckit import Inject

from browsertunnel.features.browser.domain import Browser
from browsertunnel.features.browser.presentation.rpc.channel import channel
from browsertunnel.features.browser.presentation.rpc.models import (
    ClipboardResult,
    TextParams,
)


class ClipboardMethod(StrEnum):
    COPY = "browser.clipboard.copy"
    READ = "browser.clipboard.read"
    WRITE = "browser.clipboard.write"


@channel.method(ClipboardMethod.COPY)
async def copy(browser: Inject[Browser]) -> ClipboardResult:
    return ClipboardResult(text=await browser.clipboard.copy())


@channel.method(ClipboardMethod.READ)
async def read(browser: Inject[Browser]) -> ClipboardResult:
    return ClipboardResult(text=await browser.clipboard.read())


@channel.method(ClipboardMethod.WRITE)
async def write(params: TextParams, browser: Inject[Browser]) -> None:
    await browser.clipboard.write(params.text)

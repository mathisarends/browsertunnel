from enum import StrEnum

import pyrpckit as rpc

from backend.application import BrowserClipboard
from backend.presentation.rpc.models import (
    ClipboardResult,
    TextParams,
)


class ClipboardMethod(StrEnum):
    COPY = "browser.clipboard.copy"
    READ = "browser.clipboard.read"
    WRITE = "browser.clipboard.write"


class ClipboardMethods(rpc.RpcHandler):
    def __init__(self, clipboard: BrowserClipboard) -> None:
        self._clipboard = clipboard

    @rpc.method(ClipboardMethod.COPY)
    async def copy(self) -> ClipboardResult:
        return ClipboardResult(text=await self._clipboard.copy())

    @rpc.method(ClipboardMethod.READ)
    async def read(self) -> ClipboardResult:
        return ClipboardResult(text=await self._clipboard.read())

    @rpc.method(ClipboardMethod.WRITE)
    async def write(self, params: TextParams) -> None:
        await self._clipboard.write(params.text)

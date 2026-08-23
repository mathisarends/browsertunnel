from enum import StrEnum

import pyrpckit as rpc

from backend.application import Browser
from backend.presentation.rpc.models import (
    ClipboardResult,
    EmptyParams,
    TextParams,
)


class ClipboardMethod(StrEnum):
    READ = "browser.clipboard.read"
    WRITE = "browser.clipboard.write"


class ClipboardMethods(rpc.RpcHandler):
    def __init__(self, browser: Browser) -> None:
        self._browser = browser

    @rpc.method(ClipboardMethod.READ)
    async def read(self, _params: EmptyParams) -> ClipboardResult:
        return ClipboardResult(text=await self._browser.read_clipboard())

    @rpc.method(ClipboardMethod.WRITE)
    async def write(self, params: TextParams) -> None:
        await self._browser.write_clipboard(params.text)

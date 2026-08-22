"""Start the real browser adapter once and verify its CDP connection."""

import asyncio
from contextlib import aclosing

from backend.infrastructure.cdp_browser import CdpBrowserTunnel
from backend.settings import BrowserSettings


async def main() -> None:
    browser = CdpBrowserTunnel(BrowserSettings(_env_file=None))
    await browser.start()
    try:
        tabs = await browser.list_tabs()
        print(f"CDP connected with {len(tabs)} tab(s)")
        await browser.navigate("data:text/html,<title>BrowserTunnel</title>")
        async with aclosing(browser.frames()) as frames:
            frame = await asyncio.wait_for(anext(frames), timeout=5)
            print(f"Screencast received ({len(frame.data)} base64 characters)")
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

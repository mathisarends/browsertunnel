"""Start the real browser adapter once and verify its CDP connection."""

import asyncio
from contextlib import aclosing

from backend.application import FrameReceived, NavigationChanged
from backend.infrastructure.cdp_browser import CdpBrowserTunnel
from backend.settings import BrowserSettings


async def main() -> None:
    browser = CdpBrowserTunnel(BrowserSettings(_env_file=None))
    await browser.start()
    try:
        tabs = await browser.list_tabs()
        print(f"CDP connected with {len(tabs)} tab(s)")
        await browser.navigate("data:text/html,<title>BrowserTunnel</title>")
        async with aclosing(browser.events()) as events:
            frame_received = False
            navigation_received = False
            while True:
                event = await asyncio.wait_for(anext(events), timeout=5)
                if isinstance(event, FrameReceived):
                    print(f"Screencast received ({len(event.data)} JPEG bytes)")
                    frame_received = True
                elif isinstance(event, NavigationChanged):
                    print(f"Navigation state received ({event.url})")
                    navigation_received = True
                if frame_received and navigation_received:
                    break
    finally:
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())

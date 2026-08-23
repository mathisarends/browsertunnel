"""Start the real browser adapter once and verify its CDP connection."""

import asyncio
from contextlib import aclosing

from backend.application import NavigationChanged
from backend.infrastructure.cdp_browser import CdpBrowser
from backend.settings import BrowserSettings


async def next_navigation(events) -> NavigationChanged:
    while True:
        event = await anext(events)
        if isinstance(event, NavigationChanged):
            return event


async def main() -> None:
    browser = CdpBrowser(BrowserSettings(_env_file=None))
    await browser.start()
    try:
        tabs = await browser.list_tabs()
        print(f"CDP connected with {len(tabs)} tab(s)")
        async with (
            aclosing(browser.events()) as events,
            aclosing(browser.screencast_frames()) as frames,
        ):
            navigation_task = asyncio.create_task(next_navigation(events))
            frame_task = asyncio.create_task(anext(frames))
            await asyncio.sleep(0)
            await browser.navigate("data:text/html,<title>BrowserTunnel</title>")
            navigation, frame = await asyncio.wait_for(
                asyncio.gather(navigation_task, frame_task), timeout=5
            )
            print(f"Navigation state received ({navigation.url})")
            print(f"Screencast received ({len(frame.data)} JPEG bytes)")
    finally:
        await browser.stop()


if __name__ == "__main__":
    asyncio.run(main())

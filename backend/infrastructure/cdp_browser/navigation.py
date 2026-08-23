from backend.application import BrowserNavigation
from backend.infrastructure.cdp_browser.active_target import ActiveTarget


class CdpNavigation(BrowserNavigation):
    def __init__(self, target: ActiveTarget) -> None:
        self._target = target

    async def navigate(self, url: str) -> None:
        await self._target.session().page.navigate(url=url)

    async def back(self) -> None:
        await self._walk_history(-1)

    async def forward(self) -> None:
        await self._walk_history(1)

    async def reload(self, *, ignore_cache: bool = False) -> None:
        await self._target.session().page.reload(ignore_cache=ignore_cache)

    async def stop(self) -> None:
        await self._target.session().page.stop_loading()

    async def _walk_history(self, offset: int) -> None:
        session = self._target.session()
        history = await session.page.get_navigation_history()
        index = history.current_index + offset
        if 0 <= index < len(history.entries):
            await session.page.navigate_to_history_entry(
                entry_id=history.entries[index].id
            )

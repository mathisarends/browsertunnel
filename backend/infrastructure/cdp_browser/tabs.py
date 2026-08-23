from backend.application import BrowserTab, BrowserTabNotFoundError, BrowserTabs
from backend.infrastructure.cdp_browser.active_target import ActiveTarget, SelectTarget


async def select_any_page(
    target: ActiveTarget, select: SelectTarget, *, exclude: str | None = None
) -> None:
    """Mirror some other page, opening a blank one when none is left."""
    remaining = [
        page for page in await target.page_targets() if page.target_id != exclude
    ]
    if remaining:
        await select(remaining[0].target_id)
        return
    created = await target.client().target.create_target(url="about:blank")
    await select(created.target_id)


class CdpTabs(BrowserTabs):
    def __init__(self, target: ActiveTarget, select: SelectTarget) -> None:
        self._target = target
        self._select = select

    async def list(self) -> list[BrowserTab]:
        return [
            BrowserTab(
                id=page.target_id,
                title=page.title,
                url=page.url,
                active=page.target_id == self._target.target_id,
            )
            for page in await self._target.page_targets()
        ]

    async def create(self, url: str) -> list[BrowserTab]:
        created = await self._target.client().target.create_target(url=url)
        await self._select(created.target_id)
        return await self.list()

    async def activate(self, tab_id: str) -> list[BrowserTab]:
        await self._select(tab_id)
        return await self.list()

    async def close(self, tab_id: str) -> list[BrowserTab]:
        pages = await self._target.page_targets()
        if not any(page.target_id == tab_id for page in pages):
            raise BrowserTabNotFoundError(tab_id)
        await self._target.client().target.close_target(target_id=tab_id)
        if tab_id == self._target.target_id:
            await select_any_page(self._target, self._select, exclude=tab_id)
        return await self.list()

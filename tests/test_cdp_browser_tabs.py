from types import SimpleNamespace

import pytest

from backend.infrastructure.cdp_browser.tabs import CdpTabs


def page(tab_id: str) -> SimpleNamespace:
    return SimpleNamespace(target_id=tab_id, title=tab_id, url="about:blank")


class FakeTargetDomain:
    def __init__(self, pages: list[SimpleNamespace]) -> None:
        self.pages = pages

    async def create_target(self, *, url: str) -> SimpleNamespace:
        created = page("new-tab")
        self.pages.insert(0, created)
        return created


class FakeActiveTarget:
    def __init__(self) -> None:
        self.target_id = "tab-2"
        self.pages = [page("tab-1"), page("tab-2"), page("tab-3")]
        self.target_domain = FakeTargetDomain(self.pages)

    async def page_targets(self) -> list[SimpleNamespace]:
        return self.pages

    def client(self) -> SimpleNamespace:
        return SimpleNamespace(target=self.target_domain)


@pytest.mark.asyncio
async def test_create_places_new_tab_to_the_right_of_the_active_tab() -> None:
    target = FakeActiveTarget()

    async def select(tab_id: str) -> None:
        target.target_id = tab_id

    tabs = CdpTabs(target, select)

    result = await tabs.create("about:blank")

    assert [tab.id for tab in result] == ["tab-1", "tab-2", "new-tab", "tab-3"]
    assert [tab.id for tab in result if tab.active] == ["new-tab"]


@pytest.mark.asyncio
async def test_discovered_tab_is_inserted_to_the_right_of_the_active_tab() -> None:
    target = FakeActiveTarget()
    tabs = CdpTabs(target, lambda tab_id: None)
    await tabs.list()
    target.pages.insert(0, page("popup"))

    result = await tabs.list()

    assert [tab.id for tab in result] == ["tab-1", "tab-2", "popup", "tab-3"]

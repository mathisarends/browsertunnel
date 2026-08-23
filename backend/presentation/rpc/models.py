from enum import StrEnum
from typing import Literal

import pyrpckit as rpc
from pydantic import BaseModel, ConfigDict, Field

from backend.application import BrowserTab, ClickEventType, CursorStyle, KeyEventType


class RpcModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class BrowserEventType(StrEnum):
    FRAME = "browser.frame"
    TABS = "browser.tabs"
    NAVIGATION = "browser.navigation"
    CURSOR = "browser.cursor"
    TARGET_CRASHED = "browser.targetCrashed"
    TARGET_DETACHED = "browser.targetDetached"


class EmptyParams(RpcModel):
    pass


class EmptyResult(RpcModel):
    pass


class NavigateParams(RpcModel):
    url: str = Field(min_length=1)


class ReloadParams(RpcModel):
    ignore_cache: bool = Field(default=False, alias="ignoreCache")


class ClickParams(RpcModel):
    type: ClickEventType
    x: float
    y: float
    button: Literal["left", "middle", "right", "back", "forward"]
    buttons: int = Field(ge=0)
    modifiers: int = Field(default=0, ge=0)
    click_count: int = Field(default=1, alias="clickCount", ge=0)


class HoverParams(RpcModel):
    x: float
    y: float
    buttons: int = Field(default=0, ge=0)
    modifiers: int = Field(default=0, ge=0)


class ScrollParams(RpcModel):
    x: float
    y: float
    delta_x: float = Field(alias="deltaX")
    delta_y: float = Field(alias="deltaY")


class KeyParams(RpcModel):
    type: KeyEventType
    key: str
    code: str = ""
    text: str | None = None
    modifiers: int = Field(default=0, ge=0)
    auto_repeat: bool = Field(default=False, alias="autoRepeat")


class TextParams(RpcModel):
    text: str


class TabParams(RpcModel):
    tab_id: str = Field(alias="tabId", min_length=1)


class CreateTabParams(RpcModel):
    url: str = "about:blank"


class TabResult(RpcModel):
    id: str
    title: str
    url: str
    active: bool


class TabsResult(RpcModel):
    tabs: list[TabResult]


class ClipboardResult(RpcModel):
    text: str


@rpc.event
class BrowserFrameEvent(RpcModel):
    type: Literal[BrowserEventType.FRAME] = BrowserEventType.FRAME
    data: str


@rpc.event
class BrowserTabsEvent(RpcModel):
    type: Literal[BrowserEventType.TABS] = BrowserEventType.TABS
    tabs: list[TabResult]


@rpc.event
class BrowserNavigationEvent(RpcModel):
    type: Literal[BrowserEventType.NAVIGATION] = BrowserEventType.NAVIGATION
    tab_id: str = Field(alias="tabId")
    title: str
    url: str
    loading: bool
    can_go_back: bool = Field(alias="canGoBack")
    can_go_forward: bool = Field(alias="canGoForward")
    error: str | None = None


@rpc.event
class BrowserCursorEvent(RpcModel):
    type: Literal[BrowserEventType.CURSOR] = BrowserEventType.CURSOR
    tab_id: str = Field(alias="tabId")
    cursor: CursorStyle


@rpc.event
class BrowserTargetCrashedEvent(RpcModel):
    type: Literal[BrowserEventType.TARGET_CRASHED] = BrowserEventType.TARGET_CRASHED
    tab_id: str = Field(alias="tabId")
    status: str
    error_code: int = Field(alias="errorCode")


@rpc.event
class BrowserTargetDetachedEvent(RpcModel):
    type: Literal[BrowserEventType.TARGET_DETACHED] = BrowserEventType.TARGET_DETACHED
    tab_id: str | None = Field(alias="tabId")


type BrowserEvent = (
    BrowserFrameEvent
    | BrowserTabsEvent
    | BrowserNavigationEvent
    | BrowserCursorEvent
    | BrowserTargetCrashedEvent
    | BrowserTargetDetachedEvent
)


def tabs_result(tabs: list[BrowserTab]) -> TabsResult:
    return TabsResult(
        tabs=[
            TabResult(id=tab.id, title=tab.title, url=tab.url, active=tab.active)
            for tab in tabs
        ]
    )

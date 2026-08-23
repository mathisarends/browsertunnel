import asyncio
import base64
from types import SimpleNamespace
from typing import cast

import pytest
from cdpify import CDPSession

from backend.application import ScreencastFrame
from backend.infrastructure.events import EventBus
from backend.infrastructure.screencast_event_bridge import ScreencastEventBridge


class FakePage:
    def __init__(self) -> None:
        self.started_with: dict | None = None
        self.acked: list[int] = []
        self.stop_count = 0

    async def start_screencast(self, **kwargs) -> None:
        self.started_with = kwargs

    async def screencast_frame_ack(self, *, session_id: int) -> None:
        self.acked.append(session_id)

    async def stop_screencast(self) -> None:
        self.stop_count += 1


class FakeSession:
    def __init__(self, data: bytes) -> None:
        self.page = FakePage()
        self._data = data

    async def listen(self, *_args):
        yield SimpleNamespace(
            data=base64.b64encode(self._data).decode("ascii"), session_id=7
        )
        await asyncio.Future()


@pytest.mark.asyncio
async def test_screencast_bridge_pumps_and_acknowledges_cdp_frames() -> None:
    event_bus = EventBus()
    bridge = ScreencastEventBridge(event_bus, quality=70, width=1600, height=900)
    queue = bridge.subscribe()
    session = FakeSession(b"jpeg")

    await bridge.start(cast(CDPSession, session))
    frame = await asyncio.wait_for(queue.get(), timeout=1)
    await asyncio.sleep(0)
    await bridge.stop()

    assert frame == ScreencastFrame(b"jpeg")
    assert session.page.started_with == {
        "format": "jpeg",
        "quality": 70,
        "max_width": 1600,
        "max_height": 900,
    }
    assert session.page.acked == [7]
    assert session.page.stop_count == 1


@pytest.mark.asyncio
async def test_screencast_bridge_keeps_only_latest_frame_per_subscriber() -> None:
    event_bus = EventBus()
    bridge = ScreencastEventBridge(event_bus, quality=70, width=1600, height=900)
    queue = bridge.subscribe()

    await event_bus.dispatch(ScreencastFrame(b"old"))
    await event_bus.dispatch(ScreencastFrame(b"latest"))

    assert queue.qsize() == 1
    assert queue.get_nowait() == ScreencastFrame(b"latest")

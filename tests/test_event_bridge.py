import asyncio
from dataclasses import dataclass
from typing import cast

import pytest
from cdpify import Client
from cdpify.domains.target.events import TargetCrashedEvent as CdpTargetCrashedEvent
from cdpify.domains.target.events import TargetEvent

from backend.application import TargetCrashed
from backend.infrastructure.event_bus import EventBus
from backend.infrastructure.listener_event_bridge import ListenerEventBridge


@dataclass(frozen=True)
class ExampleEvent:
    value: int


class FakeListenerSource:
    def __init__(self) -> None:
        self.event_names: set[str] = set()
        self.queues: dict[str, asyncio.Queue[object]] = {}

    async def listen[T](
        self,
        event_name: str,
        event_type: type[T],
        timeout: float | None = None,
    ):
        self.event_names.add(event_name)
        queue = self.queues.setdefault(event_name, asyncio.Queue())
        while True:
            yield cast(T, await queue.get())

    async def emit(self, event_name: str, event: object) -> None:
        await self.queues[event_name].put(event)


@pytest.mark.asyncio
async def test_event_bus_dispatches_typed_events_and_waits_with_predicate() -> None:
    event_bus = EventBus()
    received: list[int] = []

    async def collect(event: ExampleEvent) -> None:
        received.append(event.value)

    event_bus.subscribe(ExampleEvent, collect)
    waiting = asyncio.create_task(
        event_bus.wait_for_event(
            ExampleEvent,
            timeout=1,
            predicate=lambda event: event.value == 2,
        )
    )
    await asyncio.sleep(0)

    await event_bus.dispatch(ExampleEvent(1))
    await event_bus.dispatch(ExampleEvent(2))

    assert await waiting == ExampleEvent(2)
    assert received == [1, 2]


@pytest.mark.asyncio
async def test_target_bridge_owns_cdp_listener_registration() -> None:
    event_bus = EventBus()
    source = FakeListenerSource()
    bridge = ListenerEventBridge(event_bus)
    await bridge.start(cast(Client, source))
    try:
        assert source.event_names == {
            event.value
            for event in (
                TargetEvent.TARGET_CREATED,
                TargetEvent.TARGET_DESTROYED,
                TargetEvent.TARGET_INFO_CHANGED,
                TargetEvent.TARGET_CRASHED,
                TargetEvent.DETACHED_FROM_TARGET,
            )
        }

        domain_events: list[object] = []

        async def collect(event: object) -> None:
            domain_events.append(event)

        event_bus.subscribe_all(collect)
        waiting = asyncio.create_task(
            event_bus.wait_for_event(TargetCrashed, timeout=1)
        )
        await asyncio.sleep(0)
        cdp_event = CdpTargetCrashedEvent(
            target_id="tab-1", status="crashed", error_code=7
        )
        await source.emit(TargetEvent.TARGET_CRASHED, cdp_event)

        translated = await waiting
        assert translated == TargetCrashed("tab-1", "crashed", 7)
        assert domain_events == [translated]
        assert cdp_event not in domain_events
    finally:
        await bridge.stop()

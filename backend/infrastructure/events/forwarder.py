import asyncio

from backend.application import (
    BrowserEvent,
    NavigationChanged,
    TabsChanged,
    TargetCrashed,
    TargetDetached,
)
from backend.infrastructure.events.bus import EventBus


class BrowserEventForwarder:
    """Fans every event on an EventBus out to per-subscriber queues."""

    def __init__(self, event_bus: EventBus, *, maxsize: int = 16) -> None:
        self._maxsize = maxsize
        self._subscribers: set[asyncio.Queue[BrowserEvent]] = set()
        for event_type in (
            TabsChanged,
            NavigationChanged,
            TargetCrashed,
            TargetDetached,
        ):
            event_bus.on(event_type, self._forward)

    def subscribe(self) -> asyncio.Queue[BrowserEvent]:
        queue: asyncio.Queue[BrowserEvent] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[BrowserEvent]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: BrowserEvent) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    async def _forward(self, event: BrowserEvent) -> None:
        self.publish(event)

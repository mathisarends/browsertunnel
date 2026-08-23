import asyncio
from typing import cast

from backend.application import BrowserEvent, FrameReceived
from backend.infrastructure.events.bus import EventBus


class BrowserEventForwarder:
    """Fans every event on an EventBus out to per-subscriber queues."""

    def __init__(self, event_bus: EventBus, *, maxsize: int = 16) -> None:
        self._maxsize = maxsize
        self._subscribers: set[asyncio.Queue[BrowserEvent]] = set()
        event_bus.on_all(self._forward)

    def subscribe(self) -> asyncio.Queue[BrowserEvent]:
        queue: asyncio.Queue[BrowserEvent] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[BrowserEvent]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: BrowserEvent) -> None:
        for queue in tuple(self._subscribers):
            if isinstance(event, FrameReceived) and queue.full():
                continue
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    async def _forward(self, event: object) -> None:
        self.publish(cast(BrowserEvent, event))

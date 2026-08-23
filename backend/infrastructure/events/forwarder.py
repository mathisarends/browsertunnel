import asyncio
from typing import cast

from backend.application import BrowserStreamItem, ScreencastFrame
from backend.infrastructure.events.bus import EventBus


class BrowserEventForwarder:
    """Fans every event on an EventBus out to per-subscriber queues."""

    def __init__(self, event_bus: EventBus, *, maxsize: int = 16) -> None:
        self._maxsize = maxsize
        self._subscribers: set[asyncio.Queue[BrowserStreamItem]] = set()
        event_bus.on_all(self._forward)

    def subscribe(self) -> asyncio.Queue[BrowserStreamItem]:
        queue: asyncio.Queue[BrowserStreamItem] = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[BrowserStreamItem]) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: BrowserStreamItem) -> None:
        for queue in tuple(self._subscribers):
            if isinstance(event, ScreencastFrame) and queue.full():
                continue
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(event)

    async def _forward(self, event: object) -> None:
        self.publish(cast(BrowserStreamItem, event))

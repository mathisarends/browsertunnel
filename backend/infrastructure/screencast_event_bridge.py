import asyncio
import base64
import logging
from contextlib import suppress

from cdpify import CDPSession
from cdpify.domains.page.events import PageEvent, ScreencastFrameEvent

from backend.application import ScreencastFrame
from backend.infrastructure.events import EventBus

logger = logging.getLogger(__name__)


class ScreencastEventBridge:
    """Bridge CDP screencast frames onto the application event bus."""

    def __init__(
        self,
        event_bus: EventBus,
        *,
        quality: int,
        width: int,
        height: int,
        queue_size: int = 1,
    ) -> None:
        if queue_size < 1:
            raise ValueError("Screencast queue size must be at least 1")
        self._event_bus = event_bus
        self._quality = quality
        self._width = width
        self._height = height
        self._queue_size = queue_size
        self._session: CDPSession | None = None
        self._task: asyncio.Task[None] | None = None
        self._subscribers: set[asyncio.Queue[ScreencastFrame]] = set()
        event_bus.on(ScreencastFrame, self._forward)

    async def start(self, session: CDPSession) -> None:
        await self.stop()
        await session.page.start_screencast(
            format="jpeg",
            quality=self._quality,
            max_width=self._width,
            max_height=self._height,
        )
        self._session = session
        self._task = asyncio.create_task(
            self._pump(session), name="active-page:screencast"
        )

    async def stop(self) -> None:
        session = self._session
        self._session = None
        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        elif task is None and session is not None:
            with suppress(Exception):
                await session.page.stop_screencast()

    def subscribe(self) -> asyncio.Queue[ScreencastFrame]:
        queue: asyncio.Queue[ScreencastFrame] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[ScreencastFrame]) -> None:
        self._subscribers.discard(queue)

    async def _pump(self, session: CDPSession) -> None:
        try:
            async for event in session.listen(
                PageEvent.SCREENCAST_FRAME, ScreencastFrameEvent
            ):
                try:
                    await self._event_bus.dispatch(
                        ScreencastFrame(base64.b64decode(event.data))
                    )
                finally:
                    await session.page.screencast_frame_ack(session_id=event.session_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("CDP screencast stopped unexpectedly")
        finally:
            with suppress(Exception):
                await session.page.stop_screencast()

    async def _forward(self, frame: ScreencastFrame) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(frame)

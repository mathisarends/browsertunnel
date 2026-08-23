import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import cast

logger = logging.getLogger(__name__)

type EventHandler[T] = Callable[[T], Awaitable[None]]


class EventBus:
    """In-process async event dispatcher keyed by the concrete event type."""

    def __init__(self) -> None:
        self._handlers: dict[type[object], list[EventHandler[object]]] = {}
        self._wildcard_handlers: list[EventHandler[object]] = []

    def subscribe[T](self, event_type: type[T], handler: EventHandler[T]) -> None:
        handlers = self._handlers.setdefault(event_type, [])
        generic_handler = cast(EventHandler[object], handler)
        if generic_handler not in handlers:
            handlers.append(generic_handler)
            logger.debug("Subscribed to %s", event_type.__name__)

    def unsubscribe[T](self, event_type: type[T], handler: EventHandler[T]) -> None:
        handlers = self._handlers.get(event_type)
        if handlers is None:
            return
        generic_handler = cast(EventHandler[object], handler)
        if generic_handler in handlers:
            handlers.remove(generic_handler)
        if not handlers:
            self._handlers.pop(event_type, None)

    def subscribe_all(self, handler: EventHandler[object]) -> None:
        if handler not in self._wildcard_handlers:
            self._wildcard_handlers.append(handler)

    def unsubscribe_all(self, handler: EventHandler[object]) -> None:
        if handler in self._wildcard_handlers:
            self._wildcard_handlers.remove(handler)

    def has_subscribers[T](self, event_type: type[T]) -> bool:
        return bool(self._handlers.get(event_type) or self._wildcard_handlers)

    async def dispatch[T](self, event: T) -> T:
        handlers = [
            *self._handlers.get(type(event), ()),
            *self._wildcard_handlers,
        ]
        if not handlers:
            logger.debug("No handlers registered for %s", type(event).__name__)
            return event

        results = await asyncio.gather(
            *(handler(event) for handler in handlers),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                logger.error(
                    "Handler failed for %s: %s",
                    type(event).__name__,
                    result,
                    exc_info=(type(result), result, result.__traceback__),
                )
        return event

    async def wait_for_event[T](
        self,
        event_type: type[T],
        timeout: float | None = None,
        predicate: Callable[[T], bool] | None = None,
    ) -> T:
        future = asyncio.get_running_loop().create_future()

        async def handler(event: T) -> None:
            if not future.done() and (predicate is None or predicate(event)):
                future.set_result(event)

        self.subscribe(event_type, handler)
        try:
            if timeout is None:
                return await future
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self.unsubscribe(event_type, handler)

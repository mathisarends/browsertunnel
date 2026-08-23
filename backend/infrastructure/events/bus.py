import asyncio
import logging
from typing import cast

from backend.infrastructure.events.models import EventHandler

logger = logging.getLogger(__name__)


class EventBus:
    """In-process async event dispatcher keyed by the concrete event type."""

    def __init__(self) -> None:
        self._handlers: dict[type[object], list[EventHandler[object]]] = {}
        self._wildcard_handlers: list[EventHandler[object]] = []

    def on[T](self, event_type: type[T], handler: EventHandler[T]) -> None:
        handlers = self._handlers.setdefault(event_type, [])
        generic_handler = cast(EventHandler[object], handler)
        if generic_handler not in handlers:
            handlers.append(generic_handler)
            logger.debug("Subscribed to %s", event_type.__name__)

    def on_all(self, handler: EventHandler[object]) -> None:
        if handler not in self._wildcard_handlers:
            self._wildcard_handlers.append(handler)

    def unsubscribe[T](self, event_type: type[T], handler: EventHandler[T]) -> None:
        handlers = self._handlers.get(event_type)
        if handlers is None:
            return
        generic_handler = cast(EventHandler[object], handler)
        if generic_handler in handlers:
            handlers.remove(generic_handler)
        if not handlers:
            self._handlers.pop(event_type, None)

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

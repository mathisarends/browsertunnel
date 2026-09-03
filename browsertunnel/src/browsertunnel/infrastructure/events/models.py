from collections.abc import Awaitable, Callable

type EventHandler[T] = Callable[[T], Awaitable[None]]

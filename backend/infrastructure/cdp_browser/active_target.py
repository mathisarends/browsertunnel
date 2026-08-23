from collections.abc import Awaitable, Callable

from cdpify import CDPSession, Client

type SelectTarget = Callable[[str], Awaitable[None]]


class ActiveTarget:
    """The CDP client plus the page session the tunnel currently mirrors.

    The command namespaces share this handle instead of the browser itself, so
    switching tabs stays the one place that decides what "active" means.
    """

    def __init__(self) -> None:
        self._client: Client | None = None
        self._session: CDPSession | None = None
        self._target_id: str | None = None

    @property
    def target_id(self) -> str | None:
        return self._target_id

    def attach(self, client: Client) -> None:
        self._client = client

    def detach(self) -> Client | None:
        """Forget the mirrored page and hand back the client to shut down."""
        client = self._client
        self._client = None
        self._session = None
        self._target_id = None
        return client

    def mirror(self, session: CDPSession, target_id: str) -> None:
        self._session = session
        self._target_id = target_id

    def client(self) -> Client:
        if self._client is None:
            raise RuntimeError("Browser tunnel has not been started")
        return self._client

    def session(self) -> CDPSession:
        if self._session is None:
            raise RuntimeError("No browser tab is active")
        return self._session

    async def page_targets(self):
        targets = await self.client().target.get_targets()
        return [target for target in targets.target_infos if target.type == "page"]

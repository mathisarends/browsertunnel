import asyncio
import json
import logging
import shutil
import subprocess
import tempfile
import time
from collections.abc import AsyncIterator
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path

from cdpify import CDPSession, Client
from cdpify.domains.browser.types import PermissionDescriptor
from cdpify.domains.page.events import ScreencastFrameEvent

from backend.application import BrowserFrame, BrowserTab, BrowserTunnel
from backend.application.browser import KeyEventType, MouseEventType
from backend.settings import BrowserSettings

logger = logging.getLogger(__name__)


class BrowserStartupError(RuntimeError):
    pass


class BrowserTargetNotFoundError(LookupError):
    pass


class CdpBrowserTunnel(BrowserTunnel):
    def __init__(self, settings: BrowserSettings) -> None:
        self._settings = settings
        self._client: Client | None = None
        self._process: asyncio.subprocess.Process | None = None
        self._profile: tempfile.TemporaryDirectory[str] | None = None
        self._active_target_id: str | None = None
        self._active_session: CDPSession | None = None
        self._subscribers: set[asyncio.Queue[BrowserFrame]] = set()
        self._frame_task: asyncio.Task[None] | None = None
        self._state_lock = asyncio.Lock()

    async def start(self) -> None:
        try:
            cdp_url = self._settings.cdp_url
            if cdp_url is None:
                cdp_url = await self._launch_browser()
            self._client = Client(cdp_url)
            await self._client.connect()
            for permission in ("clipboard-read", "clipboard-write"):
                await self._client.browser.set_permission(
                    permission=PermissionDescriptor(name=permission),
                    setting="granted",
                )
            pages = await self._page_targets()
            if not pages:
                created = await self._client.target.create_target(url="about:blank")
                target_id = created.target_id
            else:
                target_id = pages[0].target_id
            await self._select_target(target_id)
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        await self._stop_frame_pump()
        if self._client is not None:
            await self._client.disconnect()
            self._client = None
        if self._process is not None and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except TimeoutError:
                self._process.kill()
                await self._process.wait()
        self._process = None
        if self._profile is not None:
            self._profile.cleanup()
            self._profile = None

    async def frames(self) -> AsyncIterator[BrowserFrame]:
        queue: asyncio.Queue[BrowserFrame] = asyncio.Queue(maxsize=2)
        async with self._state_lock:
            self._subscribers.add(queue)
        try:
            while True:
                yield await queue.get()
        finally:
            async with self._state_lock:
                self._subscribers.discard(queue)

    async def navigate(self, url: str) -> None:
        await self._session().page.navigate(url=url)

    async def mouse(
        self,
        *,
        event_type: MouseEventType,
        x: float,
        y: float,
        button: str | None,
        buttons: int | None,
        modifiers: int,
        click_count: int,
    ) -> None:
        await self._session().input.dispatch_mouse_event(
            type=event_type,
            x=x,
            y=y,
            button=button,
            buttons=buttons,
            modifiers=modifiers,
            click_count=click_count,
        )

    async def scroll(
        self, *, x: float, y: float, delta_x: float, delta_y: float
    ) -> None:
        await self._session().input.dispatch_mouse_event(
            type="mouseWheel",
            x=x,
            y=y,
            delta_x=delta_x,
            delta_y=delta_y,
        )

    async def key(
        self,
        *,
        event_type: KeyEventType,
        key: str,
        code: str,
        text: str | None,
        modifiers: int,
        auto_repeat: bool,
    ) -> None:
        await self._session().input.dispatch_key_event(
            type=event_type,
            key=key,
            code=code,
            text=text,
            modifiers=modifiers,
            auto_repeat=auto_repeat,
        )

    async def insert_text(self, text: str) -> None:
        await self._session().input.insert_text(text=text)

    async def read_clipboard(self) -> str:
        result = await self._session().runtime.evaluate(
            expression="navigator.clipboard.readText()",
            await_promise=True,
            return_by_value=True,
            user_gesture=True,
        )
        if result.exception_details is not None:
            raise RuntimeError("The page denied clipboard read access")
        return str(result.result.value or "")

    async def write_clipboard(self, text: str) -> None:
        expression = f"navigator.clipboard.writeText({json.dumps(text)})"
        result = await self._session().runtime.evaluate(
            expression=expression,
            await_promise=True,
            return_by_value=True,
            user_gesture=True,
        )
        if result.exception_details is not None:
            raise RuntimeError("The page denied clipboard write access")

    async def list_tabs(self) -> list[BrowserTab]:
        return [
            BrowserTab(
                id=target.target_id,
                title=target.title,
                url=target.url,
                active=target.target_id == self._active_target_id,
            )
            for target in await self._page_targets()
        ]

    async def create_tab(self, url: str) -> list[BrowserTab]:
        created = await self._browser().target.create_target(url=url)
        await self._select_target(created.target_id)
        return await self.list_tabs()

    async def activate_tab(self, tab_id: str) -> list[BrowserTab]:
        await self._select_target(tab_id)
        return await self.list_tabs()

    async def close_tab(self, tab_id: str) -> list[BrowserTab]:
        client = self._browser()
        pages = await self._page_targets()
        if not any(page.target_id == tab_id for page in pages):
            raise BrowserTargetNotFoundError(tab_id)
        await client.target.close_target(target_id=tab_id)
        if tab_id == self._active_target_id:
            remaining = [
                page for page in await self._page_targets() if page.target_id != tab_id
            ]
            if remaining:
                await self._select_target(remaining[0].target_id)
            else:
                created = await client.target.create_target(url="about:blank")
                await self._select_target(created.target_id)
        return await self.list_tabs()

    async def _select_target(self, target_id: str) -> None:
        client = self._browser()
        pages = await self._page_targets()
        if not any(page.target_id == target_id for page in pages):
            raise BrowserTargetNotFoundError(target_id)
        async with self._state_lock:
            await self._stop_frame_pump()
            await client.target.activate_target(target_id=target_id)
            attached = await client.target.attach_to_target(
                target_id=target_id, flatten=True
            )
            self._active_target_id = target_id
            self._active_session = client.session(attached.session_id)
            await self._active_session.page.enable()
            await self._start_frame_pump()

    async def _start_frame_pump(self) -> None:
        session = self._session()
        await session.page.start_screencast(
            format="jpeg",
            quality=self._settings.screencast_quality,
            max_width=self._settings.width,
            max_height=self._settings.height,
        )
        self._frame_task = asyncio.create_task(self._pump_frames(session))

    async def _stop_frame_pump(self) -> None:
        task = self._frame_task
        self._frame_task = None
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def _pump_frames(self, session: CDPSession) -> None:
        try:
            async for event in session.listen(
                "Page.screencastFrame", ScreencastFrameEvent
            ):
                frame = BrowserFrame(
                    data=event.data,
                    session_id=event.session_id,
                    metadata=asdict(event.metadata),
                )
                for queue in tuple(self._subscribers):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(frame)
                await session.page.screencast_frame_ack(session_id=event.session_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("CDP screencast stopped unexpectedly")
        finally:
            with suppress(Exception):
                await session.page.stop_screencast()

    async def _page_targets(self):
        targets = await self._browser().target.get_targets()
        return [target for target in targets.target_infos if target.type == "page"]

    def _browser(self) -> Client:
        if self._client is None:
            raise RuntimeError("Browser tunnel has not been started")
        return self._client

    def _session(self) -> CDPSession:
        if self._active_session is None:
            raise RuntimeError("No browser tab is active")
        return self._active_session

    async def _launch_browser(self) -> str:
        executable = self._find_executable()
        self._profile = tempfile.TemporaryDirectory(
            prefix="browsertunnel-", ignore_cleanup_errors=True
        )
        profile_path = Path(self._profile.name)
        args = [
            executable,
            "--remote-debugging-port=0",
            f"--user-data-dir={profile_path}",
            f"--window-size={self._settings.width},{self._settings.height}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ]
        if self._settings.headless:
            args.append("--headless=new")
        args.append("about:blank")
        creation_flags = subprocess.CREATE_NO_WINDOW if subprocess._mswindows else 0
        self._process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            creationflags=creation_flags,
        )
        active_port = profile_path / "DevToolsActivePort"
        deadline = time.monotonic() + self._settings.startup_timeout
        while time.monotonic() < deadline:
            if self._process.returncode is not None:
                raise BrowserStartupError("Chromium exited during startup")
            if active_port.exists():
                lines = active_port.read_text(encoding="utf-8").splitlines()
                if len(lines) >= 2:
                    return f"ws://127.0.0.1:{lines[0]}{lines[1]}"
            await asyncio.sleep(0.05)
        raise BrowserStartupError("Timed out waiting for Chromium's CDP endpoint")

    def _find_executable(self) -> str:
        candidates = [
            self._settings.executable,
            shutil.which("chromium"),
            shutil.which("chromium-browser"),
            shutil.which("google-chrome"),
            shutil.which("chrome"),
            shutil.which("msedge"),
        ]
        windows = [
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ]
        candidates.extend(str(path) for path in windows if path.exists())
        executable = next((candidate for candidate in candidates if candidate), None)
        if executable is None:
            raise BrowserStartupError(
                "No Chromium browser found; set BROWSER_EXECUTABLE or BROWSER_CDP_URL"
            )
        return executable

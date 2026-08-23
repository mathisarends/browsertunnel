import asyncio
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from backend.settings import BrowserSettings


class BrowserStartupError(RuntimeError):
    pass


class ChromeProcess:
    """Manage a local Chromium process and its temporary profile."""

    def __init__(self, settings: BrowserSettings) -> None:
        self._settings = settings
        self._process: asyncio.subprocess.Process | None = None
        self._profile: tempfile.TemporaryDirectory[str] | None = None

    async def start(self) -> str:
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
        try:
            return await self._wait_for_cdp_endpoint(profile_path)
        except BaseException:
            await self.stop()
            raise

    async def stop(self) -> None:
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

    async def _wait_for_cdp_endpoint(self, profile_path: Path) -> str:
        active_port = profile_path / "DevToolsActivePort"
        deadline = time.monotonic() + self._settings.startup_timeout
        while time.monotonic() < deadline:
            if self._process is None or self._process.returncode is not None:
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

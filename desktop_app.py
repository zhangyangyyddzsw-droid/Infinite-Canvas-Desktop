"""Windows desktop launcher for Infinite Canvas.

The existing FastAPI application remains the source of truth. This launcher
provides a native WebView2 window, owns the backend lifecycle, and redirects
all writable state away from the installed application directory.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


APP_NAME = "Infinite Canvas"
APP_DATA_FOLDER = "InfiniteCanvas"
MUTEX_NAME = r"Local\InfiniteCanvasDesktop"
DESKTOP_DATA_VERSION = "1"


def resource_root() -> Path:
    """Return the read-only application resource directory."""
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root).resolve()
    return Path(__file__).resolve().parent


def user_data_root(environment: Optional[Mapping[str, str]] = None) -> Path:
    """Resolve the writable per-user data directory."""
    env = environment if environment is not None else os.environ
    override = str(env.get("INFINITE_CANVAS_DATA_ROOT", "") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    local_app_data = str(env.get("LOCALAPPDATA", "") or "").strip()
    if local_app_data:
        return (Path(local_app_data) / APP_DATA_FOLDER).resolve()

    return (Path.home() / "AppData" / "Local" / APP_DATA_FOLDER).resolve()


def copy_missing_tree(source: Path, destination: Path) -> int:
    """Copy source files that do not already exist in destination."""
    if not source.is_dir():
        return 0

    copied = 0
    for source_path in source.rglob("*"):
        relative = source_path.relative_to(source)
        destination_path = destination / relative
        if source_path.is_dir():
            destination_path.mkdir(parents=True, exist_ok=True)
            continue
        if destination_path.exists():
            continue
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)
        copied += 1
    return copied


def prepare_user_data(resources: Path, destination: Path) -> int:
    """Create runtime directories and import existing project data once.

    Missing default workflows/data files are always seeded so a newer desktop
    build can add resources without overwriting user customizations.
    """
    destination.mkdir(parents=True, exist_ok=True)
    for relative in (
        "API",
        "assets/input",
        "assets/output",
        "assets/library",
        "assets/uploads",
        "data/canvases",
        "data/conversations",
        "data/media_previews",
        "output",
        "workflows",
    ):
        (destination / relative).mkdir(parents=True, exist_ok=True)

    copied = 0
    copied += copy_missing_tree(resources / "workflows", destination / "workflows")
    copied += copy_missing_tree(resources / "data", destination / "data")

    marker = destination / ".desktop-data-version"
    if not marker.exists():
        for relative in ("assets", "output", "API"):
            copied += copy_missing_tree(resources / relative, destination / relative)
        for filename in ("history.json", "global_config.json"):
            source_file = resources / filename
            destination_file = destination / filename
            if source_file.is_file() and not destination_file.exists():
                shutil.copy2(source_file, destination_file)
                copied += 1
        marker.write_text(DESKTOP_DATA_VERSION + "\n", encoding="utf-8")

    return copied


def create_listening_socket() -> socket.socket:
    """Reserve a loopback-only random port for Uvicorn."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    return listener


def configure_environment(data_root: Path, port: int) -> None:
    origin = f"http://127.0.0.1:{port}"
    os.environ.update(
        {
            "INFINITE_CANVAS_DESKTOP": "1",
            "INFINITE_CANVAS_DATA_ROOT": str(data_root),
            "INFINITE_CANVAS_HOST": "127.0.0.1",
            "INFINITE_CANVAS_PORT": str(port),
            "INFINITE_CANVAS_CORS_ORIGINS": origin,
        }
    )


def wait_until_ready(url: str, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    last_error: Optional[BaseException] = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if 200 <= response.status < 500:
                    return
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(0.1)
    raise RuntimeError(f"本地服务启动超时：{last_error or 'unknown error'}")


@dataclass
class BackendHandle:
    server: object
    thread: threading.Thread
    listener: socket.socket

    def stop(self, timeout: float = 8.0) -> None:
        setattr(self.server, "should_exit", True)
        self.thread.join(timeout=timeout)
        try:
            self.listener.close()
        except OSError:
            pass


def create_uvicorn_config(port: int):
    import uvicorn

    # Windowed PyInstaller apps have sys.stdout/sys.stderr set to None. The
    # default Uvicorn colour formatter probes those streams and crashes during
    # logging.config.dictConfig, so desktop builds deliberately keep logging
    # unformatted and warning-only.
    return uvicorn.Config(
        "main:app",
        host="127.0.0.1",
        port=port,
        log_level="warning",
        log_config=None,
        access_log=False,
        ws_ping_interval=None,
        ws_ping_timeout=None,
    )


def start_backend(listener: socket.socket) -> BackendHandle:
    import uvicorn

    port = int(listener.getsockname()[1])
    config = create_uvicorn_config(port)
    server = uvicorn.Server(config)
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        name="InfiniteCanvasBackend",
        daemon=True,
    )
    thread.start()
    return BackendHandle(server=server, thread=thread, listener=listener)


class WindowsSingleInstance:
    def __init__(self, name: str = MUTEX_NAME) -> None:
        self.name = name
        self.handle = None

    def acquire(self) -> bool:
        if os.name != "nt":
            return True
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        if not self.handle:
            raise ctypes.WinError()
        return kernel32.GetLastError() != 183

    def release(self) -> None:
        if self.handle and os.name == "nt":
            kernel32 = ctypes.windll.kernel32
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_bool
            kernel32.CloseHandle(self.handle)
            self.handle = None


def show_error(message: str) -> None:
    if os.name == "nt":
        ctypes.windll.user32.MessageBoxW(None, message, APP_NAME, 0x10)
    else:
        print(message, file=sys.stderr)


def run_desktop() -> int:
    instance = WindowsSingleInstance()
    if not instance.acquire():
        show_error("Infinite Canvas 已经在运行。")
        return 0

    backend: Optional[BackendHandle] = None
    try:
        resources = resource_root()
        data_root = user_data_root()
        prepare_user_data(resources, data_root)

        listener = create_listening_socket()
        port = int(listener.getsockname()[1])
        configure_environment(data_root, port)
        backend = start_backend(listener)

        url = f"http://127.0.0.1:{port}/"
        wait_until_ready(url)

        import webview

        webview.create_window(
            APP_NAME,
            url,
            width=1440,
            height=900,
            min_size=(960, 640),
        )
        webview.start(
            gui="edgechromium",
            debug=os.getenv("INFINITE_CANVAS_DEBUG", "") == "1",
            private_mode=False,
            storage_path=str(data_root / "webview"),
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - desktop entry must surface startup failures
        show_error(f"Infinite Canvas 启动失败：\n{exc}")
        return 1
    finally:
        if backend is not None:
            backend.stop()
        instance.release()


if __name__ == "__main__":
    raise SystemExit(run_desktop())

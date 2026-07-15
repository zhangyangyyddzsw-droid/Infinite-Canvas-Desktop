import os
import socket
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import desktop_app


class DesktopAppTests(unittest.TestCase):
    def test_user_data_root_prefers_explicit_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            resolved = desktop_app.user_data_root(
                {
                    "INFINITE_CANVAS_DATA_ROOT": temporary,
                    "LOCALAPPDATA": "ignored",
                }
            )
            self.assertEqual(resolved, Path(temporary).resolve())

    def test_user_data_root_uses_local_app_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            resolved = desktop_app.user_data_root({"LOCALAPPDATA": temporary})
            self.assertEqual(resolved, (Path(temporary) / "InfiniteCanvas").resolve())

    def test_prepare_user_data_copies_missing_files_without_overwrite(self):
        with tempfile.TemporaryDirectory() as resource_dir, tempfile.TemporaryDirectory() as data_dir:
            resources = Path(resource_dir)
            destination = Path(data_dir)
            (resources / "workflows").mkdir()
            (resources / "workflows" / "default.json").write_text("upstream", encoding="utf-8")
            (resources / "data").mkdir()
            (resources / "data" / "asset_library.json").write_text("{}", encoding="utf-8")
            (resources / "history.json").write_text("[]", encoding="utf-8")

            (destination / "workflows").mkdir()
            existing = destination / "workflows" / "default.json"
            existing.write_text("custom", encoding="utf-8")

            copied = desktop_app.prepare_user_data(resources, destination)

            self.assertGreaterEqual(copied, 2)
            self.assertEqual(existing.read_text(encoding="utf-8"), "custom")
            self.assertTrue((destination / "data" / "asset_library.json").is_file())
            self.assertTrue((destination / "history.json").is_file())
            self.assertTrue((destination / ".desktop-data-version").is_file())

    def test_listener_is_loopback_only_and_uses_random_port(self):
        listener = desktop_app.create_listening_socket()
        try:
            host, port = listener.getsockname()
            self.assertEqual(host, "127.0.0.1")
            self.assertGreater(port, 0)
            probe = socket.create_connection((host, port), timeout=1)
            probe.close()
        finally:
            listener.close()

    def test_configure_environment_locks_desktop_to_origin(self):
        with tempfile.TemporaryDirectory() as temporary, mock.patch.dict(os.environ, {}, clear=True):
            root = Path(temporary)
            desktop_app.configure_environment(root, 43123)
            self.assertEqual(os.environ["INFINITE_CANVAS_DESKTOP"], "1")
            self.assertEqual(os.environ["INFINITE_CANVAS_HOST"], "127.0.0.1")
            self.assertEqual(os.environ["INFINITE_CANVAS_PORT"], "43123")
            self.assertEqual(os.environ["INFINITE_CANVAS_CORS_ORIGINS"], "http://127.0.0.1:43123")
            self.assertEqual(Path(os.environ["INFINITE_CANVAS_DATA_ROOT"]), root)

    def test_uvicorn_logging_config_supports_windowed_build(self):
        with mock.patch.object(sys, "stdout", None), mock.patch.object(sys, "stderr", None):
            config = desktop_app.create_uvicorn_config(43123)
            config.configure_logging()
        self.assertIsNone(config.log_config)

    @unittest.skipUnless(os.name == "nt", "Windows named mutex test")
    def test_windows_single_instance_mutex_rejects_duplicate(self):
        name = rf"Local\InfiniteCanvasDesktopTest-{uuid.uuid4()}"
        first = desktop_app.WindowsSingleInstance(name)
        second = desktop_app.WindowsSingleInstance(name)
        try:
            self.assertTrue(first.acquire())
            self.assertFalse(second.acquire())
        finally:
            second.release()
            first.release()

    def test_window_close_stops_backend_and_releases_instance(self):
        instance = mock.Mock()
        instance.acquire.return_value = True
        listener = mock.Mock()
        listener.getsockname.return_value = ("127.0.0.1", 43123)
        backend = mock.Mock()
        fake_webview = SimpleNamespace(
            create_window=mock.Mock(),
            start=mock.Mock(),
        )

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            desktop_app, "WindowsSingleInstance", return_value=instance
        ), mock.patch.object(desktop_app, "resource_root", return_value=Path(temporary)), mock.patch.object(
            desktop_app, "user_data_root", return_value=Path(temporary)
        ), mock.patch.object(desktop_app, "prepare_user_data"), mock.patch.object(
            desktop_app, "create_listening_socket", return_value=listener
        ), mock.patch.object(desktop_app, "configure_environment"), mock.patch.object(
            desktop_app, "start_backend", return_value=backend
        ), mock.patch.object(desktop_app, "wait_until_ready"), mock.patch.dict(
            sys.modules, {"webview": fake_webview}
        ):
            result = desktop_app.run_desktop()

        self.assertEqual(result, 0)
        fake_webview.create_window.assert_called_once()
        fake_webview.start.assert_called_once()
        backend.stop.assert_called_once()
        instance.release.assert_called_once()


if __name__ == "__main__":
    unittest.main()

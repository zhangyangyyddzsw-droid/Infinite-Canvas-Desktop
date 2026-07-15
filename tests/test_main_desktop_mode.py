import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class MainDesktopModeTests(unittest.TestCase):
    def test_main_uses_writable_data_root_and_blocks_in_place_update(self):
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            env = os.environ.copy()
            env.update(
                {
                    "INFINITE_CANVAS_DESKTOP": "1",
                    "INFINITE_CANVAS_DATA_ROOT": temporary,
                    "INFINITE_CANVAS_CORS_ORIGINS": "http://127.0.0.1:43123",
                    "PYTHONDONTWRITEBYTECODE": "1",
                }
            )
            script = r'''
import json
import main
from fastapi import HTTPException

blocked = False
try:
    main.update_from_github()
except HTTPException as exc:
    blocked = exc.status_code == 409

update_check = main.check_update()

print(json.dumps({
    "app_data": main.APP_DATA_DIR,
    "data": main.DATA_DIR,
    "assets": main.ASSETS_DIR,
    "workflows": main.WORKFLOW_DIR,
    "static": main.STATIC_DIR,
    "desktop": main.DESKTOP_MODE,
    "cors": main.CORS_ALLOW_ORIGINS,
    "update_blocked": blocked,
    "update_check_disabled": update_check.get("desktop_mode") and not update_check.get("update_available") and not update_check.get("latest"),
}))
'''
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            payload = json.loads(result.stdout.strip().splitlines()[-1])
            data_root = Path(temporary).resolve()
            self.assertEqual(Path(payload["app_data"]), data_root)
            self.assertEqual(Path(payload["data"]), data_root / "data")
            self.assertEqual(Path(payload["assets"]), data_root / "assets")
            self.assertEqual(Path(payload["workflows"]), data_root / "workflows")
            self.assertNotEqual(Path(payload["static"]), data_root / "static")
            self.assertTrue(payload["desktop"])
            self.assertEqual(payload["cors"], ["http://127.0.0.1:43123"])
            self.assertTrue(payload["update_blocked"])
            self.assertTrue(payload["update_check_disabled"])


if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package.config.path_config import PathManager
import run as app_entry


class ReleasePackagingTests(unittest.TestCase):
    def test_release_files_declare_rdkit_support(self):
        project_root = Path(__file__).resolve().parents[1]
        requirements_text = (project_root / "requirements.txt").read_text(encoding="utf-8").lower()
        spec_text = (project_root / "mass_finding.spec").read_text(encoding="utf-8").lower()

        self.assertIn("rdkit", requirements_text)
        self.assertIn("rdkit.chem", spec_text)

    def test_main_calls_freeze_support_before_launching_app(self):
        call_order = []

        class FakeApp:
            def __init__(self):
                call_order.append("app")

            def mainloop(self):
                call_order.append("mainloop")

        with patch.object(app_entry.multiprocessing, "freeze_support", side_effect=lambda: call_order.append("freeze")), \
             patch.object(app_entry, "APP", FakeApp):
            app_entry.main()

        self.assertEqual(call_order, ["freeze", "app", "mainloop"])

    def test_frozen_app_uses_executable_directory_as_runtime_root(self):
        with TemporaryDirectory() as temp_dir:
            runtime_dir = Path(temp_dir) / "dist"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            fake_exe = runtime_dir / "MassFinding.exe"
            fake_exe.write_text("", encoding="utf-8")

            bundle_dir = Path(temp_dir) / "bundle"
            (bundle_dir / "package" / "config").mkdir(parents=True, exist_ok=True)
            (bundle_dir / "package" / "resources").mkdir(parents=True, exist_ok=True)

            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(fake_exe)), \
                 patch.object(sys, "_MEIPASS", str(bundle_dir), create=True):
                manager = PathManager()

            self.assertEqual(manager.root_dir, runtime_dir)
            self.assertEqual(manager.config_dir, bundle_dir / "package" / "config")
            self.assertEqual(manager.resource, bundle_dir / "package" / "resources")

    def test_frozen_app_writes_cache_to_localappdata(self):
        with TemporaryDirectory() as temp_dir:
            runtime_dir = Path(temp_dir) / "dist"
            runtime_dir.mkdir(parents=True, exist_ok=True)
            fake_exe = runtime_dir / "MassFinding.exe"
            fake_exe.write_text("", encoding="utf-8")

            bundle_dir = Path(temp_dir) / "bundle"
            (bundle_dir / "package" / "config").mkdir(parents=True, exist_ok=True)
            (bundle_dir / "package" / "resources").mkdir(parents=True, exist_ok=True)

            local_appdata = Path(temp_dir) / "LocalAppData"
            local_appdata.mkdir(parents=True, exist_ok=True)

            with patch.object(sys, "frozen", True, create=True), \
                 patch.object(sys, "executable", str(fake_exe)), \
                 patch.object(sys, "_MEIPASS", str(bundle_dir), create=True), \
                 patch.dict(os.environ, {"LOCALAPPDATA": str(local_appdata)}, clear=False):
                manager = PathManager()
                cache_path = manager.get_mass_finding_cache_path()

            self.assertTrue(cache_path.exists())
            self.assertTrue(str(cache_path).startswith(str(local_appdata)))


if __name__ == "__main__":
    unittest.main()

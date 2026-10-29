import importlib.util
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("freeze_engine", Path(__file__).parents[1] / "freeze_engine.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class WindowsSystemRuntimeTests(unittest.TestCase):
    def test_windows_10_system_runtime_is_not_redistributed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            internal = bundle / "_internal"
            internal.mkdir()
            system = ["ucrtbase.dll", "api-ms-win-core-file-l1-1-0.dll", "api-ms-win-crt-runtime-l1-1-0.dll"]
            keep = ["vcruntime140.dll", "python313.dll", "libcrypto-3.dll", "api-ms-win-core-fake.dll.backup"]
            for name in system + keep:
                (internal / name).write_bytes(b"fixture")
            nested = internal / "other"
            nested.mkdir()
            (nested / "ucrtbase.dll").write_bytes(b"fixture")
            self.assertEqual(set(mod.exclude_windows_system_runtime(bundle, "win32")), set(system))
            self.assertTrue(all((internal / name).is_file() for name in keep))
            self.assertTrue((nested / "ucrtbase.dll").is_file())

    def test_other_platform_bundles_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)
            internal = bundle / "_internal"
            internal.mkdir()
            file = internal / "ucrtbase.dll"
            file.write_bytes(b"fixture")
            self.assertEqual(mod.exclude_windows_system_runtime(bundle, "linux"), [])
            self.assertTrue(file.is_file())

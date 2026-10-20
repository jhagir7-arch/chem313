"""Focused regression checks for portable-build platform payload handling."""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


BUILD = Path(__file__).with_name("build_portable.py")
SPEC = importlib.util.spec_from_file_location("build_portable", BUILD)
assert SPEC and SPEC.loader
build_portable = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_portable)


class WindowsOsRuntimePayloadTests(unittest.TestCase):
    def test_windows_removes_only_os_ucrt_and_api_set_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            internal = bundle / "_internal"
            internal.mkdir()
            removable = [
                "api-ms-win-core-file-l1-1-0.dll",
                "API-MS-WIN-CRT-STDIO-L1-1-0.DLL",
                "ucrtbase.dll",
            ]
            retained = ["VCRUNTIME140.dll", "VCRUNTIME140_1.dll", "python313.dll", "api-ms-win-user32.dll"]
            for name in removable + retained:
                (internal / name).write_bytes(b"fixture")

            removed = build_portable.remove_windows_os_runtime_payloads(bundle, system="win32")

            self.assertEqual(removed, [f"_internal/{name}" for name in sorted(removable, key=str.lower)])
            for name in removable:
                self.assertFalse((internal / name).exists())
            for name in retained:
                self.assertTrue((internal / name).is_file())

    def test_non_windows_build_does_not_prune_payloads(self):
        with tempfile.TemporaryDirectory() as temporary:
            bundle = Path(temporary)
            payload = bundle / "_internal" / "ucrtbase.dll"
            payload.parent.mkdir()
            payload.write_bytes(b"fixture")

            self.assertEqual(build_portable.remove_windows_os_runtime_payloads(bundle, system="linux"), [])
            self.assertTrue(payload.is_file())


if __name__ == "__main__":
    unittest.main()

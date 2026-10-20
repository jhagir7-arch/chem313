"""Focused tests for Debian ownership discovery of hash-matched Linux runtimes."""
from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


HELPER = Path(__file__).with_name("prepare_linux_runtime_sources.py")
SPEC = importlib.util.spec_from_file_location("prepare_linux_runtime_sources", HELPER)
assert SPEC and SPEC.loader
prepare = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prepare)


class PackageOwnershipTests(unittest.TestCase):
    def test_package_for_falls_back_from_lib_alias_to_usr_lib(self):
        requested = Path("/lib/x86_64-linux-gnu/libgfortran.so.5")

        def fake_run(*args):
            if args[-1] == str(requested):
                raise subprocess.CalledProcessError(1, args)
            if args[-1] == "/usr/lib/x86_64-linux-gnu/libgfortran.so.5":
                return "libgfortran5:amd64: /usr/lib/x86_64-linux-gnu/libgfortran.so.5"
            raise AssertionError(args)

        with patch.object(prepare, "system_library_aliases", return_value=[
            requested, Path("/usr/lib/x86_64-linux-gnu/libgfortran.so.5")
        ]), patch.object(prepare, "run", side_effect=fake_run):
            self.assertEqual(prepare.package_for(requested), "libgfortran5")

    def test_package_for_rejects_ambiguous_owners(self):
        path = Path("/usr/lib/x86_64-linux-gnu/libgfortran.so.5.0.0")
        with patch.object(prepare, "system_library_aliases", return_value=[path]), patch.object(
            prepare, "run", return_value="libgfortran5:amd64, other-runtime:amd64: /usr/lib/x"
        ):
            with self.assertRaisesRegex(SystemExit, "expected one Ubuntu owner"):
                prepare.package_for(path)


if __name__ == "__main__":
    unittest.main()

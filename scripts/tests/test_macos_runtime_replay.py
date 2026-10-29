import hashlib
import importlib.util
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


spec = importlib.util.spec_from_file_location(
    "standalone_notices", Path(__file__).parents[1] / "collect_standalone_licenses.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class MacRuntimeReplayTests(unittest.TestCase):
    def test_replay_uses_isolated_cache_and_exact_pyinstaller_arguments(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod.sys, "platform", "darwin"):
            root = Path(tmp); source = root / "source.so"; source.write_bytes(b"original")
            config = types.ModuleType("PyInstaller.config"); config.CONF = {"cachedir": "original-cache"}
            utils = types.ModuleType("PyInstaller.building.utils")

            def replay(src, destination, **kwargs):
                self.assertEqual(src, str(source)); self.assertEqual(destination, "python3.13/lib-dynload/_ssl.so")
                self.assertEqual(kwargs, {"use_strip": False, "use_upx": False, "upx_exclude": [], "target_arch": "arm64", "codesign_identity": None, "entitlements_file": None, "strict_arch_validation": True})
                output = Path(config.CONF["cachedir"]) / "replayed.so"; output.write_bytes(b"pyinstaller output")
                return str(output)

            utils.process_collected_binary = replay
            package = types.ModuleType("PyInstaller"); building = types.ModuleType("PyInstaller.building")
            with mock.patch.dict(sys.modules, {"PyInstaller": package, "PyInstaller.config": config, "PyInstaller.building": building, "PyInstaller.building.utils": utils}):
                actual = mod.macos_pyinstaller_replay_sha256(source, "python3.13/lib-dynload/_ssl.so", "EXTENSION")

            self.assertEqual(actual, hashlib.sha256(b"pyinstaller output").hexdigest())
            self.assertEqual(config.CONF, {"cachedir": "original-cache"})

    def test_replayed_digest_accepts_matching_runtime_extension_and_rejects_tamper(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod.sys, "platform", "darwin"):
            root = Path(tmp); runtime = root / "runtime"; site = root / "site"; site.mkdir()
            source = runtime / "lib" / "python3.13" / "lib-dynload" / "_ssl.cpython-313-darwin.so"
            source.parent.mkdir(parents=True); source.write_bytes(b"original mach-o")
            toc = root / "COLLECT-00.toc"
            destination = "python3.13/lib-dynload/_ssl.cpython-313-darwin.so"
            toc.write_text(repr([(destination, str(source), "EXTENSION")]), encoding="utf-8")
            bundle = root / "bundle"; packaged = bundle / "_internal" / destination
            packaged.parent.mkdir(parents=True); packaged.write_bytes(b"replayed mach-o")
            runtime_notice = {"notices": [{"path": "python-runtime/LICENSE.txt"}]}
            owners = {"by_sha": {}, "by_path": {}}

            with mock.patch.object(mod, "macos_pyinstaller_replay_sha256", return_value=mod.sha256(packaged)):
                mapped = mod.pyinstaller_toc(toc, site, owners, runtime, runtime_notice, root / "out", root)
            rows = mod.native(bundle, owners, runtime_notice, mapped)
            self.assertEqual(rows[0]["owner"], "CPython")
            self.assertEqual(rows[0]["mapping_method"], mod.MACOS_CPYTHON_RUNTIME_MAPPING)

            packaged.write_bytes(b"tampered")
            rows = mod.native(bundle, owners, runtime_notice, mapped)
            self.assertEqual(rows[0]["owner"], "UNMAPPED")

    def test_openssl_is_bounded_to_runtime_lib_and_copies_terms(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod.sys, "platform", "darwin"):
            root = Path(tmp); runtime = root / "runtime"; source = runtime / "lib" / "libssl.3.dylib"
            source.parent.mkdir(parents=True); source.write_bytes(b"openssl source")
            (source.parent / "libcrypto.3.dylib").write_bytes(b"OpenSSL 3.0.21 9 Jun 2026")
            retained = root / "desktop" / "licenses" / "portable-runtime"; retained.mkdir(parents=True)
            (retained / "OPENSSL-3.0.21-LICENSE.txt").write_text("terms", encoding="utf-8")
            (retained / "OPENSSL-3.0.21-PROVENANCE.txt").write_text("source provenance", encoding="utf-8")
            output = root / "out"

            owner = mod.macos_cpython_runtime_owner(source, runtime, output, root)
            self.assertEqual(owner["owner"], "OpenSSL-3.0.21")
            self.assertEqual(len(owner["notices"]), 2)
            self.assertIsNone(mod.macos_cpython_runtime_owner(runtime / "lib" / "nested" / "libssl.3.dylib", runtime, output, root))
            (source.parent / "libcrypto.3.dylib").write_bytes(b"OpenSSL 3.0.20 10 Apr 2025")
            self.assertIsNone(mod.macos_cpython_runtime_owner(source, runtime, output, root))

    def test_ncurses_requires_diagnosed_version_and_retains_replay_digest(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(mod.sys, "platform", "darwin"):
            root = Path(tmp); runtime = root / "runtime"; site = root / "site"; site.mkdir()
            source = runtime / "lib" / "libncurses.6.dylib"; source.parent.mkdir(parents=True)
            source.write_bytes(b"Mach-O\x00ncurses 6.5.20240427\x00")
            retained = root / "desktop" / "licenses" / "portable-runtime"; retained.mkdir(parents=True)
            (retained / "NCURSES-6.5.20240427-LICENSE.txt").write_text("terms", encoding="utf-8")
            (retained / "NCURSES-6.5.20240427-PROVENANCE.txt").write_text("provenance", encoding="utf-8")
            toc = root / "COLLECT-00.toc"; toc.write_text(repr([("libncurses.6.dylib", str(source), "BINARY")]), encoding="utf-8")
            bundle = root / "bundle"; packaged = bundle / "_internal" / "libncurses.6.dylib"
            packaged.parent.mkdir(parents=True); packaged.write_bytes(b"replayed ncurses")
            owners = {"by_sha": {}, "by_path": {}}

            with mock.patch.object(mod, "macos_pyinstaller_replay_sha256", return_value=mod.sha256(packaged)):
                mapped = mod.pyinstaller_toc(toc, site, owners, runtime, {"notices": []}, root / "out", root)
            rows = mod.native(bundle, owners, {"notices": []}, mapped)
            self.assertEqual(rows[0]["owner"], "ncurses-6.5.20240427")
            self.assertEqual(rows[0]["macos_pyinstaller_replay_sha256"], mod.sha256(packaged))

            source.write_bytes(b"Mach-O\x00ncurses 6.5.20240504\x00")
            self.assertIsNone(mod.macos_ncurses_runtime_owner(source, runtime, root / "out2", root))


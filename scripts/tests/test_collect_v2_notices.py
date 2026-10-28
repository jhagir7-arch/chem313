import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('notices', Path(__file__).parents[1] / 'collect_v2_notices.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class NoticeTests(unittest.TestCase):
    def test_npm_distinguishes_versions_and_missing_notices(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); app = root / 'app'; mods = app / 'node_modules'; out = root / 'out'
            lock = {'packages': {'': {}, 'node_modules/foo': {'version': '1'}, 'node_modules/bar': {'version': '2'}, 'node_modules/dev': {'version': '3', 'dev': True}}}
            app.mkdir(); (app / 'package-lock.json').write_text(json.dumps(lock))
            for name, ver in [('foo','1'), ('bar','2'), ('dev','3')]:
                p = mods / name; p.mkdir(parents=True); (p / 'package.json').write_text(json.dumps({'name': name, 'version': ver, 'license': 'MIT'}))
            (mods / 'foo' / 'LICENSE').write_text('permission')
            rows, errors = mod.npm(app, out, root)
            self.assertEqual([r['name'] for r in rows], ['bar', 'foo'])
            self.assertEqual(len(errors), 1)
            self.assertEqual(rows[1]['notices'][0]['sha256'], mod.sha256(mods / 'foo' / 'LICENSE'))
    def test_rust_missing_license_is_an_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); crate = root / 'crate'; crate.mkdir(); (crate / 'Cargo.toml').write_text('')
            meta = {'packages': [{'id': 'one', 'name': 'example', 'version': '1', 'source': 'registry+https://example', 'manifest_path': str(crate / 'Cargo.toml'), 'license': 'MIT'}], 'resolve': {'nodes': [{'id': 'one'}]}}
            rows, errors = mod.rust(meta, root / 'out')
            self.assertEqual(rows[0]['license_expression'], 'MIT')
            self.assertEqual(len(errors), 1)

class RustFallbackTests(unittest.TestCase):
    def test_fallback_requires_matching_version_revision_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vendor = root / 'vendor' / 'x-1'; vendor.mkdir(parents=True)
            f = vendor / 'LICENSE'; f.write_text('upstream notice')
            (vendor / 'provenance.json').write_text(json.dumps({'name': 'x', 'version': '1', 'revision': 'abc', 'complete': True, 'files': [{'path': 'LICENSE', 'sha256': mod.sha256(f), 'url': 'https://example.com/LICENSE'}]}))
            self.assertEqual(len(mod.rust_fallback(vendor, root / 'out', root / 'out', 'x', '1', 'abc')), 2)
            self.assertEqual(mod.rust_fallback(vendor, root / 'out', root / 'out', 'x', '1', 'other'), [])
            f.write_text('tampered')
            self.assertEqual(mod.rust_fallback(vendor, root / 'out', root / 'out', 'x', '1', 'abc'), [])

class FrozenTests(unittest.TestCase):
    def test_missing_frozen_inputs_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result, errors = mod.frozen_assets(root / 'missing', root / 'missing.toc', root, root / 'out', root, {'notices': []})
            self.assertTrue(errors)
            self.assertEqual(result['native'], [])

    def test_bootloader_notice_requires_exception_and_hashes_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); exe = root / 'chem313-engine'; exe.write_bytes(b'engine')
            lic = root / 'COPYING.txt'; lic.write_text('GPL only')
            row, errors = mod.bootloader(exe, lic, '6.0', root / 'out')
            self.assertTrue(errors)
            lic.write_text('GPL with Bootloader Exception')
            row, errors = mod.bootloader(exe, lic, '6.0', root / 'out')
            self.assertFalse(errors)
            self.assertEqual(row['executable_sha256'], mod.sha256(exe))

    def test_unmapped_native_file_fails_release_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bundle = root / 'engine'; bundle.mkdir(); site = root / 'site'; site.mkdir()
            (bundle / 'mystery.so').write_bytes(b'unknown library')
            toc = root / 'COLLECT-00.toc'; toc.write_text('[]')
            result, errors = mod.frozen_assets(bundle, toc, site, root / 'out', root, {'notices': []})
            self.assertEqual(result['native'][0]['owner'], 'UNMAPPED')
            self.assertTrue(any('mystery.so' in error for error in errors))

class NoticeNameTests(unittest.TestCase):
    def test_source_code_named_copying_is_not_a_license(self):
        self.assertFalse(mod.is_notice(Path('copying.rs')))
        self.assertFalse(mod.is_notice(Path('LICENSE.js')))
        self.assertTrue(mod.is_notice(Path('LICENSE-MIT')))
        self.assertTrue(mod.is_notice(Path('COPYING.txt')))

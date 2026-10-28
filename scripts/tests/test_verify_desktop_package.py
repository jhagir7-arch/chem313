import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('package_check', Path(__file__).parents[1] / 'verify_desktop_package.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PackageNoticeTests(unittest.TestCase):
    def fixture(self, root):
        text = b'Exact upstream license text\n'
        (root / 'LICENSE').write_bytes(text)
        record = {'path': 'LICENSE', 'bytes': len(text), 'sha256': hashlib.sha256(text).hexdigest()}
        (root / 'inventory.json').write_text(json.dumps({'errors': [], 'project': [record]}), encoding='utf-8')
        return record

    def test_packaged_bytes_are_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); self.fixture(root)
            self.assertEqual(mod.verify_notices(root), 1)
            (root / 'LICENSE').write_bytes(b'corrupt')
            with self.assertRaisesRegex(RuntimeError, 'integrity'):
                mod.verify_notices(root)

    def test_escaping_notice_and_incomplete_inventory_block_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); record = self.fixture(root)
            record['path'] = '../outside'
            (root / 'inventory.json').write_text(json.dumps({'errors': [], 'project': [record]}), encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'escapes'):
                mod.verify_notices(root)
            (root / 'inventory.json').write_text(json.dumps({'errors': ['missing license'], 'project': []}), encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                mod.verify_notices(root)


if __name__ == '__main__':
    unittest.main()

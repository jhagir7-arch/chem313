
"""Release-candidate checks independent of native Avogadro hardware."""
import os
import json
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from hypothesislab.avogadro import ping
from hypothesislab.cli import bounded_utf8
from hypothesislab.engine import Engine
from hypothesislab.validation import InputError

class RC1Hardening(unittest.TestCase):
    def test_cli_bounded_file(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'oversized.csv'
            f.write_bytes(b'x'*250001)
            with self.assertRaisesRegex(InputError, '250 KB'):
                bounded_utf8(str(f))

    def test_cli_non_utf8_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f=Path(td)/'invalid.mol'
            f.write_bytes(b'\xff')
            with self.assertRaisesRegex(InputError, 'UTF-8'):
                bounded_utf8(str(f))

    def test_workspace_root_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'real').mkdir()
            try:
                (root/'linked').symlink_to(root/'real',target_is_directory=True)
            except OSError:
                self.skipTest('No symlink support')
            with self.assertRaisesRegex(InputError,'symlink'):
                Engine(root/'linked')

    @unittest.skipUnless(os.name=='posix','Unix sockets are POSIX only')
    def test_ping_requires_exact_pong(self):
        for response in [
            {'jsonrpc':'2.0','id':1,'result':None},
            {'jsonrpc':'2.0','id':1,'error':{'code':-32601,'message':'Not found'}},
            {'jsonrpc':'2.0','id':1,'result':'pong','error':{}},
            {'jsonrpc':'1.0','id':1,'result':'pong'},
        ]:
            with self.subTest(response=response), tempfile.TemporaryDirectory() as d:
                server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                server.bind(str(Path(d)/'avogadro'));server.listen(1)
                def service():
                    with server.accept()[0] as conn:
                        n=struct.unpack('>I',conn.recv(4))[0]
                        data=b''
                        while len(data)<n: data+=conn.recv(n-len(data))
                        payload=json.dumps(response).encode()
                        conn.sendall(struct.pack('>I',len(payload))+payload)
                t=threading.Thread(target=service,daemon=True);t.start()
                try:
                    with patch('hypothesislab.avogadro.tempfile.gettempdir',return_value=d):
                        with self.assertRaises(ConnectionError):ping(timeout=2)
                finally:
                    t.join(3);server.close()

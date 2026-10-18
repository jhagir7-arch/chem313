"""No Avogadro dependency: tests framed JSON-RPC over an isolated fake socket."""
import json
import os
import socket
import struct
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from hypothesislab.avogadro import ping

@unittest.skipUnless(os.name=='posix','Unix sockets require POSIX')
class AvogadroContractTests(unittest.TestCase):
    def test_ping_mock(self):
        with tempfile.TemporaryDirectory() as d:
            server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
            server.bind(str(Path(d)/'avogadro'))
            server.listen(1)
            received=[]
            def service():
                with server.accept()[0] as conn:
                    header=conn.recv(4)
                    n,=struct.unpack('>I',header)
                    packet=b''
                    while len(packet)<n:
                        packet+=conn.recv(n-len(packet))
                    received.append(json.loads(packet))
                    answer=json.dumps({'jsonrpc':'2.0','id':1,'result':'pong'}).encode()
                    conn.sendall(struct.pack('>I',len(answer))+answer)
            thread=threading.Thread(target=service,daemon=True)
            thread.start()
            with patch('hypothesislab.avogadro.tempfile.gettempdir', return_value=d):
                r=ping()
            thread.join(3)
            server.close()
            self.assertEqual(received[0]['method'],'internalPing')
            self.assertEqual(r['rpc_result'],'pong')
            self.assertEqual(r['host_command_execution'],'NOT_TESTED')
    def test_host_absent_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('hypothesislab.avogadro.tempfile.gettempdir',return_value=d):
                self.assertEqual(ping()['status'],'NOT_RUNNING_OR_UNREACHABLE')

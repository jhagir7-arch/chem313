"""Compile-time C++ Avogadro framed-RPC transport check against a synthetic local socket.
This is NOT a real Avogadro application/plugin test.
"""
from pathlib import Path
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading


def check(binary: str, response=None, must_succeed=True):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'avogadro'
        server=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(path))
        server.listen(1)
        received=[]
        def respond():
            with server.accept()[0] as conn:
                hdr=conn.recv(4)
                length,=struct.unpack('>I',hdr)
                body=b''
                while len(body)<length:
                    body+=conn.recv(length-len(body))
                received.append(json.loads(body))
                answer=json.dumps(response if response is not None else {'jsonrpc':'2.0','id':1,'result':'pong'}).encode()
                conn.sendall(struct.pack('>I',len(answer))+answer)
        t=threading.Thread(target=respond,daemon=True);t.start()
        proc=subprocess.run([binary],capture_output=True,text=True,env={**os.environ,'TMPDIR':d},timeout=10)
        t.join(5);server.close()
        assert (proc.returncode == 0) == must_succeed, (proc.stdout,proc.stderr)
        assert received[0]['method']=='internalPing',received
        if must_succeed:
            assert json.loads(proc.stdout)['result']=='pong',proc.stdout
        print(json.dumps({'status':'PASS_MOCK_ONLY' if must_succeed else 'REJECTED_INVALID_MOCK', 'method':received[0]['method'], 'native_avogadro':'NOT_RUN'}))

if __name__=='__main__':
    check(sys.argv[1])
    check(sys.argv[1], {'jsonrpc':'2.0','id':1,'error':{'code':-32601}},must_succeed=False)
    check(sys.argv[1], {'jsonrpc':'2.0','id':1,'result':'not-pong'},must_succeed=False)

#!/usr/bin/env python3
"""Offline HTTP MCP contract tests using a synthetic stdio server."""
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

GATEWAY = Path(__file__).with_name('kc-mcp-http.py')


class HttpGatewayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.token = 'test-token-' + 'a' * 42
        token_file = root / 'token'
        token_file.write_text(cls.token)
        token_file.chmod(0o600)
        stdio = root / 'stdio'
        stdio.write_text('''#!/bin/sh
read -r request
printf '%s' "$request" | python3 -c 'import json,sys; q=json.load(sys.stdin); print(json.dumps({"jsonrpc":"2.0","id":q["id"],"result":{"tools":[{"name":"test"}]}}))'
''')
        stdio.chmod(0o700)
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        cls.port = sock.getsockname()[1]
        sock.close()
        env = dict(os.environ, KC_MCP_HTTP_PORT=str(cls.port),
                   KC_MCP_HTTP_TOKEN_FILE=str(token_file), KC_MCP_STDIO_COMMAND=str(stdio))
        cls.proc = subprocess.Popen([sys.executable, str(GATEWAY)], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                conn = socket.create_connection(('127.0.0.1', cls.port), timeout=.1)
                conn.close()
                break
            except OSError:
                time.sleep(.025)
        else:
            raise AssertionError('MCP gateway did not start')

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.communicate(timeout=3)
        cls.tmp.cleanup()

    def request(self, method='POST', path='/mcp/dashboard', body=None, auth=True, **headers):
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=3)
        hdrs = {'Content-Type': 'application/json'}
        if auth:
            hdrs['Authorization'] = 'Bearer ' + self.token
        hdrs.update(headers)
        conn.request(method, path, body=body, headers=hdrs)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def test_valid_rpc(self):
        status, data = self.request(body=b'{"jsonrpc":"2.0","id":1,"method":"tools/list"}')
        self.assertEqual(status, 200)
        self.assertIn(b'"name":"test"', data)

    def test_auth_and_origin(self):
        self.assertEqual(self.request(body=b'{}', auth=False)[0], 401)
        self.assertEqual(self.request(body=b'{}', Origin='https://attacker.example')[0], 403)

    def test_reject_invalid_method_and_missing_server(self):
        self.assertEqual(self.request(body=b'{"message":1}')[0], 400)
        self.assertEqual(self.request(path='/mcp/secret', body=b'{}')[0], 404)
        self.assertEqual(self.request(method='GET')[0], 405)

    def test_notifications(self):
        self.assertEqual(self.request(body=b'{"jsonrpc":"2.0","method":"notifications/initialized"}')[0], 202)

    def test_reject_oversized_body(self):
        # Send the headers only: the gateway correctly rejects before accepting
        # the oversized body and immediately closes the connection.
        with socket.create_connection(('127.0.0.1', self.port), timeout=3) as sock:
            sock.sendall((
                'POST /mcp/dashboard HTTP/1.1\r\n'
                'Host: 127.0.0.1\r\n'
                'Content-Type: application/json\r\n'
                'Authorization: Bearer ' + self.token + '\r\n'
                'Content-Length: 1048577\r\n'
                '\r\n'
            ).encode())
            status_line = sock.recv(4096).split(b'\r\n', 1)[0]
        self.assertIn(b' 413 ', status_line)


if __name__ == '__main__':
    unittest.main()

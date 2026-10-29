#!/usr/bin/env python3
"""Loopback-only, bearer-authenticated, stateless Streamable HTTP to MCP stdio.

Configure KC_MCP_CONTEXT / KC_MCP_NAMESPACE / KC_MCP_DEPLOYMENT for the
kubectl-backed stdio launcher. Never bind the HTTP listener to a public IP.
"""
import hmac
import json
import os
import pathlib
import subprocess
import threading
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_REQUEST = 1024 * 1024
MAX_RESPONSE = 4 * 1024 * 1024
ALLOWED_SERVERS = frozenset(("dashboard", "memory", "agent-orchestrator"))


def configure():
    path = pathlib.Path(os.environ["KC_MCP_HTTP_TOKEN_FILE"]).expanduser()
    if path.is_symlink() or not path.is_file() or (path.stat().st_mode & 0o077):
        raise ValueError("token file must be a regular non-symlink file with mode 0600")
    token = path.read_text(encoding="utf-8").strip()
    if len(token) < 32 or any(x.isspace() for x in token):
        raise ValueError("token must have at least 32 non-whitespace characters")
    port = int(os.environ.get("KC_MCP_HTTP_PORT", "8765"))
    if not 1 <= port <= 65535:
        raise ValueError("KC_MCP_HTTP_PORT out of range")
    timeout = int(os.environ.get("KC_MCP_HTTP_TIMEOUT", "120"))
    if not 5 <= timeout <= 300:
        raise ValueError("KC_MCP_HTTP_TIMEOUT must be 5..300 seconds")
    script = os.environ.get("KC_MCP_STDIO_COMMAND") or str(
        pathlib.Path(__file__).resolve().with_name("kc-mcp-stdio.sh"))
    if not pathlib.Path(script).is_file():
        raise ValueError("MCP stdio launcher not found")
    origins = frozenset(filter(None, os.environ.get("KC_MCP_HTTP_ALLOWED_ORIGINS", "").split(",")))
    return token, port, timeout, script, origins


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    token = ""
    timeout_seconds = 120
    stdio_script = ""
    allowed_origins = frozenset()
    slots = threading.BoundedSemaphore(8)

    def log_message(self, format_string, *args):
        # No headers, request bodies, prompts or provider secrets in logs.
        print("mcp-http " + (format_string % args), file=sys.stderr)

    def reply(self, code, payload=None, *, headers=None):
        self.close_connection = True
        data = b"" if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(data)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if data:
            self.wfile.write(data)

    def do_GET(self):
        self.reply(405, {"error": "GET/SSE not supported; use MCP POST"}, headers={"Allow": "POST"})

    def do_DELETE(self):
        self.reply(405, {"error": "stateless MCP gateway has no session"}, headers={"Allow": "POST"})

    def do_OPTIONS(self):
        self.reply(405, {"error": "browser CORS not enabled"}, headers={"Allow": "POST"})

    def do_POST(self):
        if self.path not in {"/mcp/" + name for name in ALLOWED_SERVERS}:
            self.reply(404, {"error": "unknown MCP server"})
            return
        origin = self.headers.get("Origin")
        if origin and origin not in self.allowed_origins:
            self.reply(403, {"error": "Origin not allowed"})
            return
        auth = self.headers.get("Authorization", "")
        if not hmac.compare_digest(auth, "Bearer " + self.token):
            self.reply(401, {"error": "invalid bearer token"},
                       headers={"WWW-Authenticate": "Bearer"})
            return
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
            self.reply(411, {"error": "single Content-Length required"})
            return
        try:
            length = int(lengths[0])
        except ValueError:
            self.reply(400, {"error": "invalid Content-Length"})
            return
        if not 0 < length <= MAX_REQUEST:
            self.reply(413, {"error": "MCP request too large"})
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
            self.reply(415, {"error": "application/json required"})
            return
        self.connection.settimeout(15)
        try:
            raw = self.rfile.read(length)
            request = json.loads(raw)
        except (OSError, ValueError, UnicodeDecodeError):
            self.reply(400, {"error": "invalid JSON request"})
            return
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str):
            self.reply(400, {"error": "JSON-RPC 2.0 request required"})
            return
        if "id" not in request or request["id"] is None:
            # JSON-RPC notifications must not receive a response.
            self.reply(202)
            return
        if not self.slots.acquire(blocking=False):
            self.reply(429, {"error": "too many concurrent MCP requests"})
            return
        try:
            server = self.path.removeprefix("/mcp/")
            try:
                result = subprocess.run(
                    [self.stdio_script, server],
                    input=json.dumps(request, separators=(",", ":")) + "\n",
                    text=True, capture_output=True, timeout=self.timeout_seconds,
                    check=False,
                )
                if result.returncode:
                    raise RuntimeError("stdio MCP exit failure")
                if len(result.stdout.encode("utf-8")) > MAX_RESPONSE:
                    raise RuntimeError("stdio MCP response exceeds limit")
                lines = result.stdout.strip().splitlines()
                if len(lines) != 1:
                    raise RuntimeError("invalid MCP stdio response framing")
                response = json.loads(lines[0])
                if not isinstance(response, dict) or response.get("jsonrpc") != "2.0" or response.get("id") != request["id"]:
                    raise RuntimeError("unexpected MCP response envelope")
            except (OSError, ValueError, subprocess.TimeoutExpired, RuntimeError):
                self.reply(502, {"error": "MCP backend unavailable or invalid"})
                return
            self.reply(200, response)
        finally:
            self.slots.release()


def main():
    token, port, timeout, script, origins = configure()
    Handler.token = token
    Handler.timeout_seconds = timeout
    Handler.stdio_script = script
    Handler.allowed_origins = origins
    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print("MCP HTTP gateway listening on loopback port " + str(port), file=sys.stderr)
        server.serve_forever()


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError) as exc:
        sys.exit("MCP gateway configuration error: " + str(exc))

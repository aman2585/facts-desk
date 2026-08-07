#!/usr/bin/env python3
"""Serve the Antar UI and proxy /ask (and /health) to the Facts Desk API.

No changes to src/ — keeps the browser same-origin so SSE works without CORS.

Usage (API already running on :8000):
  python ui/serve.py
  # open http://127.0.0.1:5173/
"""

from __future__ import annotations

import argparse
import http.client
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

UI_ROOT = Path(__file__).resolve().parent


class Handler(BaseHTTPRequestHandler):
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def do_OPTIONS(self) -> None:
        if self.path.startswith("/ask") or self.path.startswith("/health"):
            self.send_response(204)
            self._cors()
            self.end_headers()
            return
        self.send_error(404)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/health", "/ask"):
            self._proxy()
            return
        self._static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/ask":
            self._proxy()
            return
        self.send_error(404)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Session-Id, Accept")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Expose-Headers", "X-Session-Id")

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        conn = http.client.HTTPConnection(self.api_host, self.api_port, timeout=300)
        headers = {
            k: v
            for k, v in self.headers.items()
            if k.lower()
            not in {"host", "content-length", "connection", "transfer-encoding"}
        }
        try:
            conn.request(self.command, self.path, body=body, headers=headers)
            upstream = conn.getresponse()
        except OSError as exc:
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            msg = (
                '{"type":"api_error","text":'
                f'"Cannot reach API at {self.api_host}:{self.api_port} ({exc}). '
                'Start it with: python -m src.api.cli"}'
            )
            self.wfile.write(msg.encode("utf-8"))
            return

        self.send_response(upstream.status)
        for key, val in upstream.getheaders():
            if key.lower() in {"transfer-encoding", "connection", "content-encoding"}:
                continue
            self.send_header(key, val)
        self.end_headers()
        try:
            while True:
                chunk = upstream.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        finally:
            upstream.close()
            conn.close()

    def _static(self, path: str) -> None:
        rel = path.lstrip("/") or "index.html"
        if ".." in rel.split("/"):
            self.send_error(400)
            return
        target = (UI_ROOT / rel).resolve()
        if not str(target).startswith(str(UI_ROOT.resolve())):
            self.send_error(400)
            return
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self.send_error(404)
            return
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Antar UI + proxy /ask")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=8000)
    args = parser.parse_args()

    Handler.api_host = args.api_host
    Handler.api_port = args.api_port
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"UI  http://{args.host}:{args.port}/\n"
        f"API proxy → http://{args.api_host}:{args.api_port}/ask\n"
        f"(Start API separately: python -m src.api.cli)",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

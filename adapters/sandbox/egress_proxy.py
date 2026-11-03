"""Minimal HTTP/HTTPS proxy with a host:port allowlist."""
from __future__ import annotations

import argparse
import os
import select
import socket
from http.client import HTTPConnection, HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOP_BY_HOP = {
    "connection",
    "proxy-connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "content-length",
}


class ProxyHandler(BaseHTTPRequestHandler):
    allow: set[str] = set()

    def do_GET(self) -> None:  # noqa: N802
        self._proxy()

    def do_POST(self) -> None:  # noqa: N802
        self._proxy()

    def do_PUT(self) -> None:  # noqa: N802
        self._proxy()

    def do_PATCH(self) -> None:  # noqa: N802
        self._proxy()

    def do_DELETE(self) -> None:  # noqa: N802
        self._proxy()

    def do_HEAD(self) -> None:  # noqa: N802
        self._proxy()

    def do_CONNECT(self) -> None:  # noqa: N802
        host, _, port_text = self.path.partition(":")
        port = int(port_text or "443")
        if f"{host}:{port}" not in self.allow:
            self.send_error(403, "host not allowed")
            return

        try:
            upstream = socket.create_connection((host, port), timeout=30)
        except OSError as exc:
            self.send_error(502, str(exc))
            return

        self.send_response(200, "Connection Established")
        self.end_headers()
        sockets = [self.connection, upstream]
        try:
            while True:
                readable, _, _ = select.select(sockets, [], [], 60)
                if not readable:
                    return
                for current in readable:
                    data = current.recv(65536)
                    if not data:
                        return
                    target = upstream if current is self.connection else self.connection
                    target.sendall(data)
        finally:
            upstream.close()

    def _proxy(self) -> None:
        if self.path == "/health":
            self._send(200, b"ok")
            return

        parsed = urlparse(self.path)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            self.send_error(400, "absolute URL required")
            return

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if f"{parsed.hostname}:{port}" not in self.allow:
            self.send_error(403, "host not allowed")
            return

        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in HOP_BY_HOP
        }
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"

        connection_class = HTTPSConnection if parsed.scheme == "https" else HTTPConnection
        connection = connection_class(parsed.hostname, port, timeout=180)
        try:
            connection.request(self.command, path, body=body, headers=headers)
            response = connection.getresponse()
            data = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in HOP_BY_HOP:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        finally:
            connection.close()

    def _send(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8888)
    parser.add_argument(
        "--allow",
        default=os.environ.get("EGRESS_ALLOW", "host.docker.internal:8086"),
        help="comma-separated host:port allowlist",
    )
    args = parser.parse_args()

    ProxyHandler.allow = {
        item.strip() for item in args.allow.split(",") if item.strip()
    }
    server = ThreadingHTTPServer((args.host, args.port), ProxyHandler)
    print(
        f"egress proxy on {args.host}:{args.port}, allow={sorted(ProxyHandler.allow)}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

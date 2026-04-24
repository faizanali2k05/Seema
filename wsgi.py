#!/usr/bin/env python3
"""
WSGI Entry Point for Gunicorn
Wraps the Seema demo-server for production deployment
"""

import importlib.util
import io
import os
import sys


if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "app")
DATA_DIR = os.path.join(BASE_DIR, "data")
DEMO_SERVER_PATH = os.path.join(APP_DIR, "demo-server.py")

sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DATA_DIR", DATA_DIR)


def _load_demo_server():
    spec = importlib.util.spec_from_file_location("demo_server", DEMO_SERVER_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load demo server from {DEMO_SERVER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo_server = _load_demo_server()


class _NonClosingBytesIO(io.BytesIO):
    def close(self):
        self.seek(0, io.SEEK_END)


class _FakeSocket:
    def __init__(self, request_bytes):
        self._reader = _NonClosingBytesIO(request_bytes)
        self._writer = _NonClosingBytesIO()

    def makefile(self, mode, *args, **kwargs):
        if "r" in mode:
            self._reader.seek(0)
            return self._reader
        if "w" in mode:
            return self._writer
        raise ValueError(f"Unsupported mode: {mode}")

    def sendall(self, data):
        self._writer.write(data)

    def close(self):
        return None

    @property
    def response_bytes(self):
        return self._writer.getvalue()


class _DummyServer:
    server_name = "seema"
    server_port = 8000


def _build_raw_request(environ):
    method = environ.get("REQUEST_METHOD", "GET")
    path = environ.get("PATH_INFO", "/") or "/"
    query_string = environ.get("QUERY_STRING", "")
    if query_string:
        path = f"{path}?{query_string}"

    body = b""
    wsgi_input = environ.get("wsgi.input")
    if wsgi_input is not None:
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError:
            content_length = 0
        if content_length > 0:
            body = wsgi_input.read(content_length)

    headers = []
    if environ.get("CONTENT_TYPE"):
        headers.append(("Content-Type", environ["CONTENT_TYPE"]))
    if body or environ.get("CONTENT_LENGTH"):
        headers.append(("Content-Length", str(len(body))))

    for key, value in environ.items():
        if not key.startswith("HTTP_"):
            continue
        header_name = key[5:].replace("_", "-").title()
        if header_name == "Content-Length":
            continue
        headers.append((header_name, value))

    if not any(name.lower() == "host" for name, _ in headers):
        host = environ.get("HTTP_HOST") or environ.get("SERVER_NAME", "localhost")
        headers.append(("Host", host))

    request_lines = [f"{method} {path} HTTP/1.1"]
    request_lines.extend(f"{name}: {value}" for name, value in headers)
    request_lines.append("")
    return "\r\n".join(request_lines).encode("utf-8") + b"\r\n" + body


def _parse_raw_response(raw_response):
    header_bytes, _, body = raw_response.partition(b"\r\n\r\n")
    header_text = header_bytes.decode("iso-8859-1")
    lines = header_text.split("\r\n")
    status_line = lines[0] if lines else "HTTP/1.1 500 Internal Server Error"
    parts = status_line.split(" ", 2)
    if len(parts) >= 3:
        status = f"{parts[1]} {parts[2]}"
    elif len(parts) == 2:
        status = f"{parts[1]} OK"
    else:
        status = "500 Internal Server Error"

    headers = []
    for line in lines[1:]:
        if not line or ":" not in line:
            continue
        name, value = line.split(":", 1)
        if name.lower() == "connection":
            continue
        headers.append((name.strip(), value.strip()))

    return status, headers, body


class WSGIApplication:
    """WSGI application wrapper for Gunicorn."""

    def __init__(self):
        self.handler_class = demo_server.RequestHandler

    def __call__(self, environ, start_response):
        try:
            fake_socket = _FakeSocket(_build_raw_request(environ))
            client_addr = (
                environ.get("REMOTE_ADDR", "127.0.0.1"),
                int(environ.get("REMOTE_PORT", "0") or "0"),
            )
            self.handler_class(fake_socket, client_addr, _DummyServer())
            status, headers, response_body = _parse_raw_response(fake_socket.response_bytes)
            start_response(status, headers)
            return [response_body]
        except Exception as e:
            import traceback

            error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
            start_response(
                "500 Internal Server Error",
                [("Content-Type", "text/plain; charset=utf-8")],
            )
            return [error_msg.encode("utf-8")]


application = WSGIApplication()

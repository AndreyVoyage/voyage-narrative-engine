#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Character Companion local server (loopback only, fake provider only).

Deliberately a SEPARATE, tiny process from the Character Lab React server
(``tools/character_lab_react_server.py``) -- Companion is a separate client and
must not share Lab's route table, debug surface, or data root. It is NOT a new
architecture: identical stdlib ``http.server`` framing, the same
transport-adapter dependency direction, the same deterministic network-free
FAKE provider. It exposes ONLY the five Companion endpoints.

    tools/character_companion_server.py   (HTTP framing)
            v
    CompanionTransport                    (JSON dict <-> service)
            v
    CompanionService                      (RuntimeService + Runtime Memory, unchanged)

Never binds anything but 127.0.0.1. Never performs a live provider call.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.character_companion import CompanionService, CompanionTransport  # noqa: E402
from services.character_companion.transport import CompanionTransportError  # noqa: E402

BIND_HOST = "127.0.0.1"
DEFAULT_PORT = 8788  # Lab React server uses 8787; keep distinct
FAKE_PROVIDER_ID = "fake"
FAKE_MODEL = "fake-companion-mvp-v1"
DEFAULT_FAKE_REPLY = "Это детерминированный тестовый ответ (fake provider)."


def build_fake_provider_factory(response: str = DEFAULT_FAKE_REPLY):
    def factory(recorder):
        def provider(messages):
            if recorder:
                recorder({"event": "request", "payload": {"model": "fake", "messages": messages}})
                recorder({"event": "response", "data": {
                    "id": "cmpl-fake-companion", "model": "fake",
                    "choices": [{"message": {"content": response}, "finish_reason": "stop"}],
                }})
            return response
        return provider
    return factory


def build_transport(*, data_root, acceptance_root=None, response: str = DEFAULT_FAKE_REPLY) -> CompanionTransport:
    repo_root = Path(__file__).resolve().parents[1]
    service = CompanionService(
        acceptance_root=acceptance_root or (repo_root / "accepted"),
        data_root=data_root,
        provider_factory=build_fake_provider_factory(response),
        provider_info={"provider_id": FAKE_PROVIDER_ID, "model": FAKE_MODEL},
    )
    return CompanionTransport(service)


class CompanionServer:
    """Loopback-only HTTP server wrapping a :class:`CompanionTransport`."""

    def __init__(self, transport: CompanionTransport, bind: str = BIND_HOST, port: int = DEFAULT_PORT) -> None:
        if bind != "127.0.0.1":
            raise ValueError("CompanionServer must bind to 127.0.0.1 only")
        self._transport = transport
        self._httpd = ThreadingHTTPServer((bind, port), self._make_handler())
        self._thread: Optional[threading.Thread] = None

    @property
    def host(self) -> str:
        return self._httpd.server_address[0]

    @property
    def port(self) -> int:
        return self._httpd.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> threading.Thread:
        thread = threading.Thread(
            target=self._httpd.serve_forever, kwargs={"poll_interval": 0.1}, daemon=True
        )
        thread.start()
        self._thread = thread
        return thread

    def shutdown(self) -> None:
        try:
            self._httpd.shutdown()
        finally:
            self._httpd.server_close()

    def _make_handler(self):
        transport = self._transport

        class Handler(BaseHTTPRequestHandler):
            server_version = "CharacterCompanion/0.1"

            def log_message(self, *args) -> None:
                pass

            def _json(self, status: int, obj) -> None:
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", 0) or 0)
                if length <= 0:
                    return {}
                raw = self.rfile.read(length)
                try:
                    data = json.loads(raw.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return {}
                return data if isinstance(data, dict) else {}

            def _call(self, fn) -> None:
                try:
                    self._json(200, fn())
                except CompanionTransportError as exc:
                    self._json(exc.status, exc.to_json())

            def _route(self, method: str, path: str, body: dict) -> None:
                parts = [p for p in path.split("/") if p]

                if method == "GET" and parts == ["health"]:
                    self._json(200, {"status": "ready", "provider": "fake", "client": "companion"})
                    return
                if method == "GET" and parts == ["api", "companion", "characters"]:
                    return self._call(transport.list_characters)
                if method == "GET" and parts[:3] == ["api", "companion", "characters"] and len(parts) == 5 \
                        and parts[4] == "sessions":
                    character_id = urllib.parse.unquote(parts[3])
                    return self._call(lambda: transport.list_sessions(character_id))
                if method == "POST" and parts == ["api", "companion", "sessions"]:
                    return self._call(lambda: transport.create_session(body))
                if method == "GET" and parts[:3] == ["api", "companion", "sessions"] and len(parts) == 5 \
                        and parts[4] == "messages":
                    session_id = urllib.parse.unquote(parts[3])
                    return self._call(lambda: transport.get_messages(session_id))
                if method == "POST" and parts == ["api", "companion", "messages"]:
                    return self._call(lambda: transport.send_message(body))

                self._json(404, {"error": {"code": "not_found", "message": "unknown route"}})

            def do_GET(self) -> None:
                self._route("GET", self.path.split("?", 1)[0], {})

            def do_POST(self) -> None:
                self._route("POST", self.path.split("?", 1)[0], self._read_json())

        return Handler


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Character Companion local server (127.0.0.1 only, fake provider only)"
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--data-root", required=True, help="durable Companion data root")
    parser.add_argument("--reply", default=DEFAULT_FAKE_REPLY)
    args = parser.parse_args(argv)

    transport = build_transport(data_root=Path(args.data_root), response=args.reply)
    server = CompanionServer(transport, port=args.port)
    print(f"[character_companion_server] listening on {server.base_url} (fake provider)")
    server.start()
    try:
        while True:
            threading.Event().wait(3600)
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
